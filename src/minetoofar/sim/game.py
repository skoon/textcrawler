"""The rules of play: walking, doors, light, fog, fighting, abilities, traps, and the scheduler
that runs the monsters."""

import hashlib
from collections.abc import Sequence
from dataclasses import replace

from minetoofar.content.balance import Balance, load_balance
from minetoofar.content.gamedata import UPGRADE_RANK, GameData, load_gamedata
from minetoofar.core.fov import compute_fov
from minetoofar.core.geometry import DIRS8, Pos, direction_to, in_rear_arc
from minetoofar.core.grid import Grid, Tile, is_walkable
from minetoofar.core.pathing import distance_map
from minetoofar.core.rng import Rng
from minetoofar.core.seed import Seed
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.gen.spawns import SpawnList
from minetoofar.gen.world import generate_world
from minetoofar.sim import ai, behaviors
from minetoofar.sim.actors import (
    Actor,
    Monster,
    Player,
    max_hp,
    new_monster,
    new_player,
    offhand_stats,
    player_stats,
)
from minetoofar.sim.combat import Outcome, Stats, resolve_attack
from minetoofar.sim.events import (
    AbilityUsed,
    ArmorDamaged,
    Attacked,
    Blocked,
    BlockReason,
    Command,
    Disarm,
    DoorOpened,
    Event,
    GraveFall,
    Killed,
    Move,
    Moved,
    Noticed,
    PlayerDied,
    PoisonTick,
    RankSet,
    Refused,
    Run,
    SetRank,
    Spoke,
    Spotted,
    StatusApplied,
    StubbornInvoked,
    ToggleTorch,
    TorchChanged,
    TorchDropped,
    TrapDisarmed,
    TrapSpotted,
    TrapTriggered,
    UseAbility,
    Wait,
    Waited,
)
from minetoofar.sim.statuses import (
    apply_status,
    cooldown_left,
    due_ticks,
    effective_cost,
    is_active,
    spend_charge,
    start_cooldown,
)
from minetoofar.sim.traps import Trap
from minetoofar.sim.views import (
    TICKS_PER_TURN,
    AbilityView,
    GameView,
    HeroView,
    MonsterView,
    TrapView,
)

__all__ = ["REMEMBERED", "TICKS_PER_TURN", "UNSEEN", "VISIBLE", "Game", "GameOver", "GameView"]

UNSEEN, REMEMBERED, VISIBLE = 0, 1, 2
_FADE = bytes([UNSEEN, REMEMBERED, REMEMBERED]) + bytes(253)  # VISIBLE -> REMEMBERED
_DOORS = (Tile.DOOR, Tile.DOOR_OPEN)
_RUN_STOPS = (Tile.DOOR_OPEN, Tile.ENTRY, Tile.EXIT)
_UNAWARE = ("asleep", "idle")  # a monster that has not noticed the player yet


class GameOver(Exception):
    """Raised when a command arrives after the player has died."""


class Game:
    def __init__(
        self,
        spec: LevelSpec,
        spawns: SpawnList,
        balance: Balance,
        data: GameData,
        rng: Rng,
        class_id: str = "fighter",
        rank: int = 1,
        traps: Sequence[Trap] = (),
        graveyard: bool = False,
    ) -> None:
        self.spec = spec
        self.data = data
        self.rng = rng
        self.graveyard = graveyard
        self.play = balance.play
        self.ai = balance.ai
        self.noises = balance.noise
        self._combat = balance.combat
        self._signature = data.classes[class_id].signature
        self.grid = Grid(spec.width, spec.height, spec.tiles)
        self.player: Player = new_player(data, class_id, rank, spec.entry)
        self.monsters: list[Monster] = [
            new_monster(
                data,
                s.kind,
                i + 1,
                s.pos,
                s.state,
                spec.level,
                s.facing,
                dict(s.speech),
                balance.ai.trapper_max_traps if data.monsters[s.kind].behavior == "trapper" else 0,
            )
            for i, s in enumerate(spawns.spawns)
        ]
        self.traps: list[Trap] = list(traps)
        self.torch_lit = False
        self.dead = False
        self.cause = ""
        self._vis = bytearray(spec.width * spec.height)
        self._dist: dict[Pos, int] | None = None
        self._flee: dict[Pos, int] | None = None
        self._look()
        self._spotted = {m.id for m in self.monsters if self.visible(m)}
        self._spot_traps(chance=False)  # a Rogue starts out seeing what is already in range
        self._spot_tick = self.ticks

    @classmethod
    def new(
        cls,
        seed: Seed,
        level: int,
        rank: int = 1,
        class_id: str = "fighter",
        armor_dur: int | None = None,
    ) -> "Game":
        """A fresh level; `armor_dur` carries worn armor in from the level above."""
        balance, data = load_balance(), load_gamedata()
        world = generate_world(seed, level, balance, data)
        traps = [Trap(pos, kind) for pos, kind in world.traps.traps]
        game = cls(
            world.spec, world.monsters, balance, data, seed.rng().derive("play", level),
            class_id, rank, traps, world.theme.graveyard,
        )  # fmt: skip
        if armor_dur is not None:
            limit = data.items.armor[game.player.body].dur
            if not 0 <= armor_dur <= limit:
                raise ValueError(f"armor_dur must be 0-{limit}, got {armor_dur}")
            game.player.body_dur = armor_dur
        return game

    @property
    def pos(self) -> Pos:
        return self.player.pos

    @property
    def ticks(self) -> int:
        return self.player.ready_at

    @property
    def light_radius(self) -> int:
        return self.play.torch_radius if self.torch_lit else self.play.hard_hat_radius

    @property
    def is_tracker(self) -> bool:
        return self._signature == "tracker"

    # -- what the UI sees ----------------------------------------------------------------

    def view(self) -> GameView:
        return GameView(
            self.spec.width,
            self.spec.height,
            self.grid.to_bytes(),
            bytes(self._vis),
            self.pos,
            self.ticks,
            self.light_radius,
            self.torch_lit,
            self.spec.level,
            self.spec.seed,
            self._hero_view(),
            tuple(self._monster_view(m) for m in self.monsters if self.visible(m)),
            tuple(self._monster_view(m) for m in self._sensed()),
            tuple(
                TrapView(t.pos, self.data.traps[t.kind].name, t.disarmed)
                for t in self.traps
                if t.revealed
            ),
            self.graveyard,
        )

    @staticmethod
    def _monster_view(m: Monster) -> MonsterView:
        return MonsterView(m.id, m.kind, m.name, m.pos, m.hp, m.max_hp)

    def _sensed(self) -> list[Monster]:
        """Tracker (Ranger): every enemy inside the sensing circle that is not in plain view."""
        if self._signature != "tracker":
            return []
        limit = self._combat.tracker_radius_sq
        return [
            m
            for m in self.monsters
            if not self.visible(m) and m.state != "buried" and _dist_sq(m.pos, self.pos) <= limit
        ]

    def _hero_view(self) -> HeroView:
        p = self.player
        c = self.data.classes[p.class_id]
        s = self._player_stats()
        damage = _damage_text(s)
        off_stats = offhand_stats(p, self.data)
        off_attack = f"ATK {off_stats.atk:+d}  DMG {_damage_text(off_stats)}" if off_stats else ""
        items = self.data.items
        off = items.weapons.get(p.offhand) or items.shields.get(p.offhand)
        armor = items.armor[p.body]
        return HeroView(
            p.name, c.name, p.rank, p.hp, p.max_hp, c.strength, c.dexterity, s.atk, s.defense,
            s.dr, damage, off_attack, p.class_id, items.weapons[p.weapon].name,
            off.name if off else "",
            items.hats[p.head].name, armor.name, p.body_dur, armor.dur, c.signature,
            self._ability_view(), self.dead, self.cause,
        )  # fmt: skip

    def _ability_view(self) -> AbilityView:
        ability_id = self.data.classes[self.player.class_id].ability
        ab = self.data.abilities[ability_id]
        left = cooldown_left(self.player, ability_id, self.ticks)
        unlocked = self.player.rank >= ab.unlock_rank
        return AbilityView(
            ab.name, ab.unlock_rank, unlocked, unlocked and left == 0,
            (left + TICKS_PER_TURN - 1) // TICKS_PER_TURN,
        )  # fmt: skip

    def state_hash(self) -> str:
        """A digest of every piece of mutable state, for replay checkpoints."""
        p = self.player
        lines = [
            f"rng {self.rng.state} torch {int(self.torch_lit)} dead {int(self.dead)}",
            f"player {p.pos.x} {p.pos.y} face {p.facing[0]} {p.facing[1]} hp {p.hp}/{p.max_hp} "
            f"rank {p.rank} dur {p.body_dur} stubborn {int(p.stubborn_used)} ready {p.ready_at} "
            f"{_status_text(p)}",
        ]
        for m in sorted(self.monsters, key=lambda mon: mon.id):
            lines.append(
                f"monster {m.id} {m.kind} {m.pos.x} {m.pos.y} face {m.facing[0]} {m.facing[1]} "
                f"hp {m.hp} {m.state} ready {m.ready_at} {_status_text(m)} "
                f"alert {m.alert_pos} since {m.since} unseen {m.unseen_since} "
                f"trap {m.last_trap}/{m.traps_left} said {sorted(m.said.items())}"
            )
        for t in self.traps:
            lines.append(f"trap {t.pos.x} {t.pos.y} {t.kind} {int(t.revealed)} {int(t.disarmed)}")
        lines.append("tiles " + hashlib.sha256(self.grid.to_bytes()).hexdigest())
        lines.append("vis " + hashlib.sha256(bytes(self._vis)).hexdigest())
        lines.append("spotted " + " ".join(str(i) for i in sorted(self._spotted)))
        return hashlib.sha256("\n".join(lines).encode("ascii")).hexdigest()

    # -- commands ------------------------------------------------------------------------

    def submit(self, command: Command) -> list[Event]:
        if self.dead:
            raise GameOver(f"the run is over: {self.cause}")
        match command:
            case Move(dx, dy):
                return self._move(_direction(dx, dy)) + self._settle()
            case Run(dx, dy):
                return self._run(_direction(dx, dy))
            case Wait():
                self._spend(self.play.wait_cost)
                return [Waited(), *self._settle()]
            case ToggleTorch():
                self.torch_lit = not self.torch_lit
                self._spend(self.play.use_cost)
                self._look()
                return [TorchChanged(self.torch_lit), *self._settle()]
            case SetRank(rank):
                hp = max_hp(self.data, self.player.class_id, rank)  # validates the rank
                self.player.rank, self.player.max_hp, self.player.hp = rank, hp, hp
                return [RankSet(rank)]
            case UseAbility():
                return self._after(self._use_ability())
            case Disarm(dx, dy):
                return self._after(self._disarm(_direction(dx, dy)))

    def _after(self, events: list[Event]) -> list[Event]:
        """Let the monsters answer, unless the command was refused and took no time."""
        if events and isinstance(events[0], Refused):
            return events
        return events + self._settle()

    def _spend(self, base: int) -> None:
        now = self.player.ready_at
        self.player.ready_at += effective_cost(self.player, base, now, self.data.statuses)

    def _look(self) -> None:
        """Fade what was in view to remembered, then mark what the lamp reaches now."""
        self._vis = bytearray(self._vis.translate(_FADE))
        width = self.spec.width
        for p in compute_fov(self.grid, self.pos, self.light_radius):
            self._vis[p.y * width + p.x] = VISIBLE

    def visible(self, m: Monster) -> bool:
        """In the player's plain view: its tile is lit and it is not buried or submerged."""
        return not m.hidden and self._vis[m.pos.y * self.spec.width + m.pos.x] == VISIBLE

    def _monster_at(self, pos: Pos) -> Monster | None:
        return next((m for m in self.monsters if m.pos == pos), None)

    # -- the player's moves --------------------------------------------------------------

    def _move(self, d: tuple[int, int]) -> list[Event]:
        dest = self.pos.step(d)
        if not self.grid.in_bounds(dest.x, dest.y):
            return [Blocked(dest, BlockReason.WALL)]
        tile = self.grid.get(dest.x, dest.y)
        diagonal = d[0] != 0 and d[1] != 0
        target = self._monster_at(dest)
        if target is not None:
            if target.hidden:
                return [Blocked(dest, BlockReason.OCCUPIED)]
            if not self._can_reach(target, d):
                return [Blocked(dest, self._block_reason(tile, diagonal))]
            return self._attack_monster(target)
        if tile == Tile.DOOR and not diagonal:
            self.grid.set(dest.x, dest.y, Tile.DOOR_OPEN)
            self.player.facing = d
            self._spend(self.play.door_cost)
            self._look()
            return [DoorOpened(dest), *self.noise(dest, self.noises.door)]
        if not self.grid.can_step(self.pos, d):
            return [Blocked(dest, self._block_reason(tile, diagonal))]
        self.player.pos, self.player.facing = dest, d
        self._spend(self.play.move_cost * self.grid.step_mult(dest.x, dest.y))
        self._look()
        events: list[Event] = [Moved(dest, tile)]
        events += self._enter_terrain(tile, dest)
        if (trap := self._live_trap_at(dest)) is not None:
            events += self._spring(trap)
        return events

    def _can_reach(self, target: Monster, d: tuple[int, int]) -> bool:
        """Melee reach: the movement rule, except that a Wraith inside a wall can be struck."""
        if self.grid.can_step(self.pos, d):
            return True
        return target.behavior == "phaser" and not is_walkable(
            self.grid.get(target.pos.x, target.pos.y)
        )

    def _player_stats(self) -> Stats:
        """Attack, defense and damage with whatever statuses are active (Soaked is DEF -1)."""
        stats = player_stats(self.player, self.data)
        bonus = self._status_defense(self.player, self.player.ready_at)
        return replace(stats, defense=stats.defense + bonus) if bonus else stats

    def _status_defense(self, actor: Actor, now: int) -> int:
        return sum(
            self.data.statuses[sid].defense
            for sid in actor.statuses
            if sid in self.data.statuses and is_active(actor, sid, now)
        )

    def _enter_terrain(self, tile: Tile, pos: Pos) -> list[Event]:
        """What the ground does to the player who just stepped onto it."""
        events: list[Event] = []
        if tile == Tile.BRINE:
            self._soak()
            if self.torch_lit and self.rng.chance(1, self.play.torch_brine_one_in):
                self.torch_lit = False
                self._look()
                events.append(TorchDropped())
        elif tile == Tile.OPEN_GRAVE:
            damage = self.rng.dice(1, self.play.grave_fall_sides)
            self.player.ready_at += self.play.grave_climb_ticks
            events += [GraveFall(pos, damage), *self._hurt_player(damage, "an open grave")]
        return events

    def _soak(self) -> None:
        apply_status(self.player, "soaked", self.player.ready_at, self.data.statuses)

    def _block_reason(self, tile: Tile, diagonal: bool) -> BlockReason:
        if not is_walkable(tile):
            return BlockReason.WALL
        if diagonal and (tile in _DOORS or self.grid.get(self.pos.x, self.pos.y) in _DOORS):
            return BlockReason.DOOR
        return BlockReason.CORNER

    def _sides(self, d: tuple[int, int]) -> tuple[bool, ...]:
        """Which tiles abreast of the heading can be stepped onto; a change means a junction."""
        return tuple(
            self.grid.can_step(self.pos, o) for o in DIRS8 if o[0] * d[0] + o[1] * d[1] == 0
        )

    def _run(self, d: tuple[int, int]) -> list[Event]:
        """Repeat a move until something changes: a refusal, a door, a landmark, a junction, or
        anything that happens around the player (a monster in view, a blow struck)."""
        events: list[Event] = []
        sides = self._sides(d)
        while True:
            ahead = self.pos.step(d)
            if (trap := self._live_trap_at(ahead)) is not None and trap.revealed:
                return events or [Blocked(ahead, BlockReason.TRAP)]
            step = self._move(d)
            if isinstance(step[-1], Blocked):
                return events or step  # only the first step reports a refusal
            around = self._settle()
            events += step + around
            if around or len(step) > 1 or not isinstance(step[-1], Moved) or self.dead:
                return events
            if any(self.visible(m) for m in self.monsters):
                return events
            if self.grid.get(self.pos.x, self.pos.y) in _RUN_STOPS:
                return events
            now = self._sides(d)
            if now != sides:
                return events
            sides = now

    # -- the player's attacks ------------------------------------------------------------

    def adjacent_enemies(self) -> list[Monster]:
        """Monsters in melee reach, clockwise from north (the movement rule applies)."""
        found = []
        for d in DIRS8:
            m = self._monster_at(self.pos.step(d))
            if m is not None and not m.hidden and self._can_reach(m, d):
                found.append(m)
        return found

    def _attack_monster(self, m: Monster) -> list[Event]:
        """A normal attack action: main hand, then the off hand if a second weapon is held."""
        self.player.facing = direction_to(self.pos, m.pos)
        main = player_stats(self.player, self.data)
        events = self._strike(m, main)
        off = offhand_stats(self.player, self.data)
        if off is not None and m in self.monsters:
            events += self._strike(m, off)
        self._spend(main.attack_cost)
        return events + self.noise(self.pos, self.noises.melee)

    def monster_stats(self, m: Monster, now: int) -> Stats:
        """What an attack against `m` meets: its statuses, and a Wraith's wall."""
        bonus = self._status_defense(m, now)
        if m.behavior == "phaser" and not is_walkable(self.grid.get(m.pos.x, m.pos.y)):
            bonus += self.ai.phaser_wall_defense
        return replace(m.stats, defense=m.stats.defense + bonus) if bonus else m.stats

    def _strike(self, m: Monster, stats: Stats, penalty: int = 0, bonus: int = 0) -> list[Event]:
        """One attack roll by the player: flanking, Backstab, the Tracker's beast bonus, poison."""
        p, c = self.player, self._combat
        now = p.ready_at
        flank = in_rear_arc(p.pos, m.pos, m.facing)
        helpless = m.state in _UNAWARE or is_active(m, "stunned", now)
        rogue = self._signature == "backstab"
        backstab = rogue and (helpless or flank or m.state == "fleeing")
        if self._signature == "tracker" and m.faction == "beast":
            bonus += c.beast_bonus
        result = resolve_attack(
            self.rng, stats, self.monster_stats(m, now), (c.flank_bonus if flank else 0) - penalty,
            auto_hit=rogue and helpless,
            bonus_dice=(c.backstab_dice, c.backstab_sides) if backstab else (0, 0),
            bonus_flat=bonus,
        )  # fmt: skip
        hit = result.damage > 0
        events: list[Event] = [
            Attacked(
                0,
                p.name,
                m.id,
                m.name,
                result.roll,
                result.outcome,
                result.damage,
                backstab and hit,
            )
        ]
        if not hit:
            return events
        power = spend_charge(p, "coated")  # every hit uses a charge, even a killing one
        m.hp -= result.damage
        if m.hp <= 0:
            self.monsters.remove(m)
            return [*events, Killed(m.id, m.name), *self.speak(m, "on_death", now)]
        if m.state not in ("hunting", "fleeing"):
            m.state = "hunting"
            events += [Noticed(m.id, m.name), *self.speak(m, "on_sight", now)]
        if m.hp * 2 < m.max_hp:
            events += self.speak(m, "on_hurt", now)
        if power is not None:
            apply_status(m, "poisoned", now, self.data.statuses, power=power)
            events.append(StatusApplied(m.id, m.name, "poisoned"))
        return events

    # -- abilities -----------------------------------------------------------------------

    def _use_ability(self) -> list[Event]:
        p = self.player
        ability_id = self.data.classes[p.class_id].ability
        ab = self.data.abilities[ability_id]
        now = p.ready_at
        if p.rank < ab.unlock_rank:
            return [Refused("locked")]
        if cooldown_left(p, ability_id, now):
            return [Refused("cooldown")]
        upgraded = p.rank >= UPGRADE_RANK
        value = ab.value_up if upgraded else ab.value
        charges = ab.charges_up if upgraded else ab.charges
        cooldown = ab.cooldown_ticks_up if upgraded else ab.cooldown_ticks
        main = player_stats(p, self.data)
        targets = self.adjacent_enemies()
        events: list[Event] = [AbilityUsed(ab.name)]
        if ab.kind == "coat":
            apply_status(p, "coated", now, self.data.statuses, power=value, charges=charges)
            self._spend(self.play.use_cost)
        elif not targets:
            return [Refused("no_target")]
        elif ab.kind == "cleave":
            for m in targets:
                p.facing = direction_to(p.pos, m.pos)
                events += self._strike(m, main, penalty=value)
            self._spend(main.attack_cost)
            events += self.noise(p.pos, self.noises.melee)
        else:  # dual_strike: both hands at full attack against the first enemy clockwise
            m = targets[0]
            p.facing = direction_to(p.pos, m.pos)
            events += self._strike(m, main, bonus=value)
            off = offhand_stats(p, self.data, penalty=0)
            if off is not None and m in self.monsters:
                events += self._strike(m, off, bonus=value)
            self._spend(main.attack_cost)
            events += self.noise(p.pos, self.noises.melee)
        start_cooldown(p, ability_id, now, cooldown)
        return events

    # -- traps ---------------------------------------------------------------------------

    def _live_trap_at(self, pos: Pos) -> Trap | None:
        return next((t for t in self.traps if t.pos == pos and not t.disarmed), None)

    def _spring(self, trap: Trap) -> list[Event]:
        """A trap goes off under the player and is spent. Damage traps lose the Hard Hat's
        reduction (never below 1); a Stun Charge does no damage but stuns."""
        d = self.data.traps[trap.kind]
        self.traps.remove(trap)
        if d.effect == "stun":
            events: list[Event] = [TrapTriggered(trap.pos, d.name, 0, trap.kind)]
            if apply_status(self.player, "stunned", self.player.ready_at, self.data.statuses):
                events.append(StatusApplied(0, self.player.name, "stunned"))
            return events
        raw = self.rng.dice(d.dice_n, d.dice_sides) + d.dmg
        damage = max(1, raw - self.data.items.hats[self.player.head].trap_reduction)
        return [
            TrapTriggered(trap.pos, d.name, damage, trap.kind),
            *self._hurt_player(damage, d.name),
        ]

    def _spot_traps(self, chance: bool = True) -> list[Event]:
        """The Rogue sees hidden traps within three tiles in plain view; everyone else has a
        one-in-three chance per turn to notice an adjacent one."""
        found: list[Event] = []
        for t in self.traps:
            if t.revealed or t.disarmed:
                continue
            if self._signature == "backstab":
                vis = self._vis[t.pos.y * self.spec.width + t.pos.x] == VISIBLE
                noticed = vis and _dist_sq(t.pos, self.pos) <= self._combat.spot_radius_sq
            else:
                near = max(abs(t.pos.x - self.pos.x), abs(t.pos.y - self.pos.y)) <= 1
                noticed = chance and near and self.rng.chance(1, self._combat.passive_spot_one_in)
            if noticed:
                t.revealed = True
                found.append(TrapSpotted(t.pos, self.data.traps[t.kind].name))
        return found

    def _disarm(self, d: tuple[int, int]) -> list[Event]:
        if self._signature != "backstab":
            return [Refused("not_rogue")]
        target = self.pos.step(d)
        trap = next(
            (t for t in self.traps if t.pos == target and t.revealed and not t.disarmed), None
        )
        if trap is None:
            return [Refused("no_trap")]
        self.player.facing = d
        trap.disarmed = True
        self._spend(self.play.door_cost)  # "Disarm: 100 ticks", the same as any ordinary action
        return [TrapDisarmed(trap.pos, self.data.traps[trap.kind].name)]

    # -- the monsters' turns -------------------------------------------------------------

    def _settle(self) -> list[Event]:
        """Run every monster whose turn comes before the player's next one (ties: player first)."""
        events: list[Event] = []
        self._dist = self._flee = None
        while not self.dead:
            due = [m for m in self.monsters if m.ready_at < self.player.ready_at]
            if not due:
                break
            events += behaviors.take_turn(self, min(due, key=lambda m: (m.ready_at, m.id)))
        if any(isinstance(e, DoorOpened) for e in events):
            self._look()  # a door opened out of the player's sight can still change what they see
        if self.grid.get(self.pos.x, self.pos.y) == Tile.BRINE:
            self._soak()  # standing in the water keeps you soaked
        if not self.dead and self.ticks != self._spot_tick:
            self._spot_tick = self.ticks  # spotting rolls once per turn, not once per keypress
            events += self._spot_traps()
        return events + self._new_sightings()

    def _new_sightings(self) -> list[Event]:
        fresh = [m for m in self.monsters if self.visible(m) and m.id not in self._spotted]
        self._spotted.update(m.id for m in fresh)
        return [Spotted(m.id, m.name) for m in fresh]

    # What the monsters' brains (sim/behaviors.py) may ask of the game.

    def spend_monster(self, m: Monster, base: int, now: int) -> None:
        m.ready_at += effective_cost(m, base, now, self.data.statuses)

    def remove(self, m: Monster) -> None:
        self.monsters.remove(m)

    def occupied(self, besides: Monster) -> set[Pos]:
        """Tiles a monster cannot step onto: everyone else's, and the player's."""
        return {o.pos for o in self.monsters if o is not besides} | {self.pos}

    def collect_poison(self, m: Monster, now: int) -> list[Event]:
        """Collect the poison damage that came due before this turn; it ignores DR."""
        events: list[Event] = []
        for damage in due_ticks(m, "poisoned", now, self.data.statuses):
            m.hp -= damage
            events.append(PoisonTick(m.id, m.name, damage))
            if m.hp <= 0:
                self.monsters.remove(m)
                events += [Killed(m.id, m.name), *self.speak(m, "on_death", now)]
                break
        return events

    def distances_for(self, m: Monster) -> dict[Pos, int]:
        """The player's distance map, computed once per settle and only as far as the awake
        monsters need it; a monster outside it (just woke up) triggers one wider recompute."""
        if self._dist is None or m.pos not in self._dist:
            awake = {o.pos for o in self.monsters if o.state != "asleep"} | {m.pos}
            self._dist = distance_map(self.grid, self.pos, until=awake)
        return self._dist

    def flee_map(self) -> dict[Pos, int]:
        """Where is safe from the player (GDD 7.7), computed once per settle on demand."""
        if self._flee is None:
            self._flee = ai.flee_map(self.grid, distance_map(self.grid, self.pos))
        return self._flee

    def noise(self, source: Pos, radius: int) -> list[Event]:
        """A sound at `source`: sleepers in earshot wake half the time, idle monsters come to
        look; the hunting, the fleeing, and the hidden pay it no mind (GDD 7.7)."""
        reach = ai.noise_reach(self.grid, source, radius)
        events: list[Event] = []
        for m in sorted(self.monsters, key=lambda mon: mon.id):
            if m.pos not in reach or m.hidden or m.state in ("hunting", "fleeing"):
                continue
            if m.state == "asleep":
                if not self.rng.chance(1, self.ai.wake_noise_one_in):
                    continue
                events.append(Noticed(m.id, m.name))
            m.state, m.alert_pos = "alerted", source
        return events

    def speak(self, m: Monster, event: str, now: int) -> list[Event]:
        """A Rogue Human's line for `event`: once only, except taunts, which repeat later."""
        text = m.speech.get(event)
        if text is None:
            return []
        last = m.said.get(event)
        repeat = self.ai.speech_hit_cooldown if event == "on_hit" else None
        if last is not None and (repeat is None or now - last < repeat):
            return []
        m.said[event] = now
        return [Spoke(m.id, m.name, text)]

    def lay_trap(self, pos: Pos) -> None:
        """Vane's trap: a random kind, hidden, where he stands."""
        self.traps.append(Trap(pos, self.rng.pick(list(self.data.traps))))

    def attack_player(self, m: Monster, situational: int = 0) -> list[Event]:
        """One swing by `m` at the player: flanking, armor wear, a dropped torch, damage."""
        flank = in_rear_arc(m.pos, self.pos, self.player.facing)
        result = resolve_attack(
            self.rng, m.stats, self._player_stats(),
            (self._combat.flank_bonus if flank else 0) + situational,
        )  # fmt: skip
        events: list[Event] = [
            Attacked(m.id, m.name, 0, self.player.name, result.roll, result.outcome, result.damage)
        ]
        if result.damage == 0:
            return events
        crit = result.outcome is Outcome.CRIT
        events += self._wear_armor(crit=crit)
        if crit and self.torch_lit and self.rng.chance(1, self.play.torch_crit_one_in):
            self.torch_lit = False  # knocked from your hand
            self._look()
            events.append(TorchDropped())
        return events + self._hurt_player(result.damage, m.name)

    def _wear_armor(self, crit: bool) -> list[Event]:
        before = self.player.body_dur
        if before <= 0:
            return []
        after = max(0, before - (2 if crit else 1))
        self.player.body_dur = after
        armor = self.data.items.armor[self.player.body]
        return [ArmorDamaged(armor.name, after, armor.dur, after == 0)]

    def _hurt_player(self, damage: int, killer: str) -> list[Event]:
        p = self.player
        hp = p.hp - damage
        if hp > 0:
            p.hp = hp
            return []
        if self.data.classes[p.class_id].signature == "stubborn" and not p.stubborn_used:
            p.hp, p.stubborn_used = 1, True
            return [StubbornInvoked()]
        p.hp, self.dead, self.cause = 0, True, killer
        return [PlayerDied(killer)]


def _direction(dx: int, dy: int) -> tuple[int, int]:
    if (dx, dy) not in DIRS8:
        raise ValueError(f"not one of the eight directions: {(dx, dy)}")
    return (dx, dy)


def _damage_text(s: Stats) -> str:
    return f"{s.dice_n}d{s.dice_sides}" + (f"{s.dmg_flat:+d}" if s.dmg_flat else "")


def _dist_sq(a: Pos, b: Pos) -> int:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def _status_text(actor: Actor) -> str:
    ends = ",".join(
        f"{k}:{s.ends}/{s.power}/{s.charges}/{s.next_tick}"
        for k, s in sorted(actor.statuses.items())
    )
    immune = ",".join(f"{k}:{v}" for k, v in sorted(actor.immune.items()))
    return f"status [{ends}] immune [{immune}]"
