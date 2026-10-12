"""The rules of play: walking, doors, light, fog, fighting, abilities, traps, and the scheduler
that runs the monsters."""

import copy
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from minetoofar.content.balance import Balance, load_balance
from minetoofar.content.docs import NAMES as DOCUMENT_NAMES
from minetoofar.content.docs import DocBook, load_docs
from minetoofar.content.gamedata import UPGRADE_RANK, GameData, load_gamedata
from minetoofar.content.loot import DOCUMENTS
from minetoofar.core.fov import compute_fov
from minetoofar.core.geometry import DIRS8, Pos, direction_to, in_rear_arc
from minetoofar.core.grid import Grid, Tile, is_walkable
from minetoofar.core.pathing import distance_map
from minetoofar.core.rng import Rng
from minetoofar.core.seed import Seed
from minetoofar.gen.drops import SupplyDrop
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.gen.loot import LootItem
from minetoofar.gen.spawns import SpawnList
from minetoofar.gen.world import generate_world
from minetoofar.sim import ai, behaviors
from minetoofar.sim.actors import (
    Actor,
    FloorItem,
    Item,
    Monster,
    Player,
    armor_max,
    max_hp,
    new_monster,
    new_player,
    offhand_stats,
    player_stats,
)
from minetoofar.sim.combat import Outcome, Stats, resolve_attack
from minetoofar.sim.economy import Account, Choices, Slip, compute_slip, score
from minetoofar.sim.events import (
    AbilityUsed,
    ArmorDamaged,
    AtCrate,
    Attacked,
    Blocked,
    BlockReason,
    Command,
    Disarm,
    DocumentRead,
    DoorOpened,
    DropItem,
    Equip,
    Equipped,
    Event,
    GraveFall,
    Healed,
    HumanDefeated,
    ItemDropped,
    ItemPicked,
    ItemUsed,
    Killed,
    Move,
    Moved,
    Noticed,
    Pickup,
    PlayerDied,
    PoisonTick,
    RankSet,
    Refused,
    Run,
    SeeHere,
    SetRank,
    Spoke,
    Spotted,
    StatusApplied,
    StubbornInvoked,
    SupplyDropped,
    SupplyTaken,
    TakeSupply,
    ToggleTorch,
    TorchBurnedOut,
    TorchChanged,
    TorchDropped,
    TrapDisarmed,
    TrapSpotted,
    TrapTriggered,
    UseAbility,
    UseItem,
    ValuableCollected,
    Wait,
    Waited,
)
from minetoofar.sim.items import KIT, TORCH, add_item, remove_one, standard_issue
from minetoofar.sim.ledger import Ledger, Repair, fold
from minetoofar.sim.statuses import (
    apply_status,
    cooldown_left,
    due_ticks,
    effective_cost,
    is_active,
    spend_charge,
    start_cooldown,
)
from minetoofar.sim.supply import Crate, Invoice, invoice
from minetoofar.sim.traps import Trap
from minetoofar.sim.views import (
    TICKS_PER_TURN,
    AbilityView,
    CrateView,
    FloorView,
    GameView,
    HeroView,
    MonsterView,
    PackLine,
    TrapView,
)

__all__ = [
    "REMEMBERED", "TICKS_PER_TURN", "UNSEEN", "VISIBLE", "Carry", "Game", "GameOver", "GameView",
]  # fmt: skip

UNSEEN, REMEMBERED, VISIBLE = 0, 1, 2
_FADE = bytes([UNSEEN, REMEMBERED, REMEMBERED]) + bytes(253)  # VISIBLE -> REMEMBERED
_DOORS = (Tile.DOOR, Tile.DOOR_OPEN)
_RUN_STOPS = (Tile.DOOR_OPEN, Tile.ENTRY, Tile.EXIT)
_UNAWARE = ("asleep", "idle")  # a monster that has not noticed the player yet


class GameOver(Exception):
    """Raised when a command arrives after the player has died."""


@dataclass(frozen=True)
class Carry:
    """What an Associate takes down the Shaft: kit, pack, torch, purse and tally."""

    player: Player
    account: Account
    cleared: int
    bounties: int
    turns: int = 0  # turns spent on the levels already finished


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
        *,
        floor: Sequence[FloorItem] = (),
        drops: Mapping[int, Sequence[Item]] | None = None,
        account: Account | None = None,
        carry: Carry | None = None,
        docs: DocBook | None = None,
        supply: Sequence[SupplyDrop] = (),
    ) -> None:
        self.spec = spec
        self.docs = docs or load_docs()
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
        self.economy = balance.economy
        self.cleared = 0  # levels finished and checked out
        self.bounties = 0
        self.turns_before = 0  # turns on earlier levels of this run
        if carry is not None:
            self._adopt(carry)
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
        self.floor: list[FloorItem] = list(floor)
        self.supply_params = balance.supply
        self.human_name = next((m.name for m in self.monsters if m.faction == "human"), "")
        self._due: list[tuple[int, SupplyDrop]] = list(enumerate(supply, 1))  # still on the way
        self.crates: list[Crate] = []
        self.drops: dict[int, list[Item]] = {k: list(v) for k, v in (drops or {}).items()}
        self.account = account or (carry.account if carry else Account())
        self.ledger = Ledger(level=spec.level, graveyard=graveyard)
        standard_issue(
            self.player.pack, data, {KIT: self.play.issue_kits, TORCH: self.play.issue_torches}
        )
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
        carry: Carry | None = None,
    ) -> "Game":
        """A fresh level. `carry` brings the Associate down from the level above; `armor_dur`
        alone just wears the starting armor."""
        balance, data = load_balance(), load_gamedata()
        if carry is not None:
            rank, class_id = carry.player.rank, carry.player.class_id
        world = generate_world(seed, level, balance, data)
        traps = [Trap(pos, kind) for pos, kind in world.traps.traps]
        floor = [FloorItem(pos, Item(*_fields(i))) for pos, i in world.loot.items]
        drops = {mid: [Item(*_fields(i))] for mid, i in world.loot.drops}
        game = cls(
            world.spec, world.monsters, balance, data, seed.rng().derive("play", level),
            class_id, rank, traps, world.theme.graveyard, floor=floor, drops=drops, carry=carry,
            supply=world.drops.drops,
        )  # fmt: skip
        if armor_dur is not None:
            limit = armor_max(data, game.player, game.player.body)
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
        lamp = self.data.items.hats[self.player.head].lamp
        return max(lamp, self.play.torch_radius) if self.torch_lit else lamp

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
            tuple(self._pack_line(i, item) for i, item in enumerate(self.player.pack)),
            tuple(
                FloorView(f.pos, f.item.id, self._name(f.item.id), self._glyph(f.item.id))
                for f in self.floor
                if self._vis[f.pos.y * self.spec.width + f.pos.x] != UNSEEN
            ),
            self.account.wallet,
            self.account.debt,
            self.account.coupons,
            -(-self.player.torch_left // TICKS_PER_TURN),
            tuple(
                CrateView(c.pos, c.number)
                for c in self.crates
                if self._vis[c.pos.y * self.spec.width + c.pos.x] != UNSEEN
            ),
        )

    def _name(self, item_id: str) -> str:
        return DOCUMENT_NAMES.get(item_id) or self.data.items.name(item_id)

    def _glyph(self, item_id: str) -> str:
        """Which map glyph a find is drawn with (GDD 5.4)."""
        if item_id in DOCUMENTS:
            return "document"
        kind = self.data.items.category(item_id)
        if kind == "valuable":
            return self.data.items.valuables[item_id].shine
        return "armor" if kind in ("armor", "shield", "hat") else kind

    def _pack_line(self, index: int, item: Item) -> PackLine:
        kind = self.data.items.category(item.id)
        top = armor_max(self.data, self.player, item.id) if kind == "armor" else 0
        name = self._name(item.id)
        return PackLine(index, item.id, name, item.qty, item.charge, kind, item.dur, top)

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
            items.hats[p.head].name, armor.name, p.body_dur, armor_max(self.data, p, p.body),
            c.signature,
            self._ability_view(), self.dead, self.cause,
            items.trinkets[p.trinket].name if p.trinket else "",
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
        lines.append(
            f"kit {p.weapon} {p.offhand} {p.head} {p.body} {p.trinket} torch {p.torch_left} "
            f"bonus {p.hp_bonus} mods {sorted(p.weapon_mods.items())} "
            f"plated {sorted(p.plated)} pack "
            + " ".join(f"{i.id}:{i.qty}:{i.charge}:{i.dur}" for i in p.pack)
        )
        a, led = self.account, self.ledger
        lines.append(
            f"purse {a.wallet} {a.debt} {int(a.repair_plan)} {int(a.hazard_waiver)} "
            f"{int(a.damage_waiver)} {a.coupons} cleared {self.cleared} {self.bounties} "
            f"turns {self.turns_before}"
        )
        lines.append(
            f"ledger {led.salvage} {led.used} {led.traps} {led.tripwires} {led.torches_dropped} "
            f"{led.clock_ins} {int(led.stubborn)} {int(led.bounty)} {led.supply}"
        )
        lines += [
            f"crate {c.pos.x} {c.pos.y} {c.number} {c.lines} {c.delivery_billed}"
            for c in self.crates
        ]
        lines.append("due " + " ".join(f"{n}:{d.trigger}" for n, d in self._due))
        lines += [
            f"floor {f.pos.x} {f.pos.y} {f.item.id}:{f.item.qty}:{f.item.charge}:{f.item.dur}:"
            f"{f.item.text}"
            for f in self.floor
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
        lit, start = self.torch_lit, self.ticks
        events = self._dispatch(command)
        if lit:
            events += self._burn(self.ticks - start)
        for event in events:
            fold(self.ledger, event, self.data)
        return events

    def _dispatch(self, command: Command) -> list[Event]:
        match command:
            case Move(dx, dy):
                return self._move(_direction(dx, dy)) + self._settle()
            case Run(dx, dy):
                return self._run(_direction(dx, dy))
            case Wait():
                self._spend(self.play.wait_cost)
                return [Waited(), *self._settle()]
            case ToggleTorch():
                return self._after(self._toggle_torch())
            case SetRank(rank):
                p = self.player
                hp = max_hp(self.data, p.class_id, rank, p.trinket, p.hp_bonus)
                self.player.rank, self.player.max_hp, self.player.hp = rank, hp, hp
                return [RankSet(rank)]
            case UseAbility():
                return self._after(self._use_ability())
            case Disarm(dx, dy):
                return self._after(self._disarm(_direction(dx, dy)))
            case Pickup():
                return self._after(self._pickup())
            case Equip(index, off_hand):
                return self._after(self._equip(index, off_hand))
            case UseItem(index):
                return self._after(self._use_item(index))
            case DropItem(index):
                return self._after(self._drop(index))
            case TakeSupply(lines):
                return self._after(self._take_supply(lines))

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
        events += self._collect_valuables(dest)
        events += self._see_here(dest)
        events += self._at_crate(dest)
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
                events.append(self._lose_torch())
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

    # -- check-out (GDD 8.6) -------------------------------------------------------------

    def _bill(self) -> Ledger:
        """The ledger as it stands, with the worn armor and the trinket filled in."""
        p, items = self.player, self.data.items
        armor = items.armor[p.body]
        most = armor_max(self.data, p, p.body)
        repair = Repair(armor.name, most - p.body_dur, armor.repair_rate)
        lanyard = bool(p.trinket and items.trinkets[p.trinket].waives)
        return replace(self.ledger, repair=repair, lanyard=lanyard, died=self.dead)

    def slip(self, choices: Choices | None = None) -> Slip:
        """The pay slip for this level as it stands. Changes nothing."""
        return compute_slip(self._bill(), self.account, choices or Choices(), self.economy)

    def check_out(self, choices: Choices | None = None) -> Slip:
        """End the level: pay the slip, make good the armor, restock Standard Issue."""
        slip = self.slip(choices)
        self.account = slip.account
        if slip.repaired:
            self.player.body_dur = armor_max(self.data, self.player, self.player.body)
        if not self.dead:
            self.cleared += 1
            standard_issue(
                self.player.pack,
                self.data,
                {KIT: self.play.issue_kits, TORCH: self.play.issue_torches},
            )
        self.bounties += int(self.ledger.bounty)
        return slip

    def score(self) -> int:
        return score(self.account, self.cleared, self.bounties, self.economy)

    def carry_over(self) -> Carry:
        return Carry(
            copy.deepcopy(self.player), self.account, self.cleared, self.bounties, self.total_turns
        )

    @property
    def total_turns(self) -> int:
        """Turns on this run so far, this level included."""
        return self.turns_before + self.ticks // TICKS_PER_TURN

    def _adopt(self, carry: Carry) -> None:
        """Arrive with what the last level left: kit, pack, torch, purse. Hit points are free."""
        c, p = carry.player, self.player
        p.weapon, p.offhand, p.head, p.body = c.weapon, c.offhand, c.head, c.body
        p.body_dur, p.trinket, p.torch_left = c.body_dur, c.trinket, c.torch_left
        p.pack = copy.deepcopy(c.pack)
        p.hp_bonus, p.plated = c.hp_bonus, set(c.plated)
        p.weapon_mods = dict(c.weapon_mods)
        p.max_hp = p.hp = max_hp(self.data, p.class_id, p.rank, p.trinket, p.hp_bonus)
        self.cleared, self.bounties, self.turns_before = carry.cleared, carry.bounties, carry.turns

    # -- supply drops (GDD 8.5) ----------------------------------------------------------

    def crate_here(self) -> Crate | None:
        return next((c for c in self.crates if c.pos == self.pos), None)

    def crate_invoice(self, taken: tuple[int, ...]) -> Invoice:
        """What taking these lines from the crate underfoot would cost."""
        crate = self.crate_here()
        if crate is None:
            raise LookupError("no crate here")
        return invoice(crate.lines, taken, not crate.delivery_billed, self.data, self.supply_params)

    def _land_drops(self) -> list[Event]:
        """A crate lands on its turn, on the nearest free floor tile within reach of the player."""
        events: list[Event] = []
        while self._due and self.ticks // TICKS_PER_TURN >= self._due[0][1].trigger:
            spot = self._landing_spot()
            if spot is None:
                break  # no room within three tiles: it falls when there is some
            number, drop = self._due.pop(0)
            self.crates.append(Crate(spot, number, list(drop.lines)))
            events.append(SupplyDropped(spot, number))
        return events

    def _landing_spot(self) -> Pos | None:
        taken = {self.pos, *(m.pos for m in self.monsters), *(f.pos for f in self.floor)}
        taken |= {t.pos for t in self.traps} | {c.pos for c in self.crates}
        reach = self.supply_params.landing_radius
        for ring in range(reach + 1):
            tiles = [
                Pos(self.pos.x + dx, self.pos.y + dy)
                for dy in range(-ring, ring + 1)
                for dx in range(-ring, ring + 1)
                if max(abs(dx), abs(dy)) == ring
            ]
            for p in tiles:  # row by row
                if (
                    self.grid.in_bounds(p.x, p.y)
                    and self.grid.get(p.x, p.y) in (Tile.FLOOR, Tile.CAVE_FLOOR)
                    and p not in taken
                ):
                    return p
        return None

    def _at_crate(self, pos: Pos) -> list[Event]:
        crate = next((c for c in self.crates if c.pos == pos), None)
        return [AtCrate(crate.number)] if crate else []

    def _take_supply(self, picks: tuple[int, ...]) -> list[Event]:
        crate = self.crate_here()
        if crate is None:
            return [Refused("no_crate")]
        if not picks:
            return [Refused("nothing_taken")]
        if len(set(picks)) != len(picks) or any(not 0 <= i < len(crate.lines) for i in picks):
            return [Refused("no_item")]
        stock = Item  # new stock arrives prepaid; new gear arrives in good condition
        goods = [
            stock(ln.item, ln.qty, 0, ln.dur) for ln in (crate.lines[i] for i in sorted(picks))
        ]
        trial = copy.deepcopy(self.player.pack)
        if not all(add_item(trial, self.data, item) for item in goods):
            return [Refused("pack_full")]
        bill = self.crate_invoice(picks)
        self.player.pack[:] = trial
        crate.lines = [ln for i, ln in enumerate(crate.lines) if i not in picks]
        crate.delivery_billed = crate.delivery_billed or bill.delivery > 0
        self.ledger.supply.append((f"Supply Drop Invoice #{crate.number}", bill.total))
        if not crate.lines:
            self.crates.remove(crate)
        self._spend(self.play.use_cost)
        return [SupplyTaken(crate.number, bill.subtotal, bill.handling, bill.delivery)]

    # -- the pack ------------------------------------------------------------------------

    def _blow_noise(self) -> int:
        """A blow is heard 5 steps away, or further with a loud weapon (a Shovel, 8)."""
        return max(self.noises.melee, self.data.items.weapons[self.player.weapon].noise)

    def _collect_valuables(self, pos: Pos) -> list[Event]:
        """Valuables jump into the pack unasked, for free; they become Salvage Credit."""
        found = [f for f in self.floor if f.pos == pos and f.item.id in self.data.items.valuables]
        events: list[Event] = []
        for f in found:
            self.floor.remove(f)
            v = self.data.items.valuables[f.item.id]
            events += [ValuableCollected(f.item.id, v.name, v.credit)] * f.item.qty
        return events

    def _see_here(self, pos: Pos) -> list[Event]:
        names = tuple(self._name(f.item.id) for f in self.floor if f.pos == pos)
        return [SeeHere(names)] if names else []

    def _slain(self, m: Monster, now: int) -> list[Event]:
        """A monster dies: it leaves its pre-rolled drop, and a Rogue Human earns the bounty."""
        self.monsters.remove(m)
        self.ledger.undead_kills += m.faction == "undead"
        self.ledger.beast_kills += m.faction == "beast"
        events: list[Event] = [Killed(m.id, m.name), *self.speak(m, "on_death", now)]
        self.floor += [FloorItem(m.pos, item) for item in self.drops.pop(m.id, [])]
        if m.faction == "human":
            events.append(HumanDefeated(m.name))
        return events

    def _pickup(self) -> list[Event]:
        here = next((f for f in self.floor if f.pos == self.pos), None)
        if here is None:
            crate = self.crate_here()
            return [AtCrate(crate.number)] if crate else [Refused("nothing_here")]
        item = here.item
        if item.id in self.data.items.valuables:
            events = self._collect_valuables(self.pos)
            self._spend(self.play.pickup_cost)
            return events
        if item.id in DOCUMENTS:
            return self._read(here)
        if not add_item(self.player.pack, self.data, item):
            return [Refused("pack_full")]
        self.floor.remove(here)
        self._spend(self.play.pickup_cost)
        return [ItemPicked(item.id, self.data.items.name(item.id), item.qty)]

    def _read(self, here: FloorItem) -> list[Event]:
        """Documents are read where they lie: a coupon goes on the account, a map on the wall."""
        self.floor.remove(here)
        self._spend(self.play.pickup_cost)
        kind = here.item.id
        if kind == "coupon":
            self.account = replace(self.account, coupons=self.account.coupons + 1)
        elif kind == "map":
            self._reveal_rooms()
        return [DocumentRead(kind, self.docs.text(kind, here.item.text))]

    def _reveal_rooms(self) -> None:
        """A map fragment marks every room (and its walls) as remembered."""
        width = self.spec.width
        for r in self.spec.rooms:
            for y in range(r.y - 1, r.y + r.h + 1):
                for x in range(r.x - 1, r.x + r.w + 1):
                    if self.grid.in_bounds(x, y) and self._vis[y * width + x] == UNSEEN:
                        self._vis[y * width + x] = REMEMBERED

    def _drop(self, index: int) -> list[Event]:
        pack = self.player.pack
        if not 0 <= index < len(pack):
            return [Refused("no_item")]
        one = remove_one(pack, index)
        self.floor.append(FloorItem(self.pos, one))
        self._spend(self.play.pickup_cost)
        return [ItemDropped(self.data.items.name(one.id))]

    def _equip(self, index: int, off_hand: bool) -> list[Event]:
        p, items = self.player, self.data.items
        if not 0 <= index < len(p.pack):
            return [Refused("no_item")]
        item = p.pack[index]
        kind = items.category(item.id)
        if kind not in ("weapon", "armor", "shield", "hat", "trinket"):
            return [Refused("not_equipment")]
        two_handed = items.weapons[p.weapon].two_handed
        slot = {"weapon": "weapon", "armor": "body", "shield": "offhand", "hat": "head"}.get(
            kind, "trinket"
        )
        if kind == "weapon" and off_hand:
            if not items.weapons[item.id].light:
                return [Refused("not_light")]
            slot = "offhand"
        if slot == "offhand" and two_handed:
            return [Refused("two_handed")]
        del p.pack[index]
        old: str = getattr(p, slot)
        if old:
            p.pack.append(Item(old, 1, 0, p.body_dur if slot == "body" else 0))
        if slot == "body":
            p.body_dur = item.dur
        setattr(p, slot, item.id)
        if slot == "weapon" and items.weapons[item.id].two_handed and p.offhand:
            p.pack.append(Item(p.offhand))  # no hand free for it
            p.offhand = ""
        if slot == "trinket":
            self._refit_hit_points(old)
        self._spend(self.play.use_cost)
        self._look()  # a hat's lamp may light more
        return [Equipped(items.name(item.id))]

    def _refit_hit_points(self, old_trinket: str) -> None:
        """A Thermos adds to the maximum and heals that much; taking it off trims to the new one."""
        p = self.player
        before = max_hp(self.data, p.class_id, p.rank, old_trinket, p.hp_bonus)
        p.max_hp = max_hp(self.data, p.class_id, p.rank, p.trinket, p.hp_bonus)
        p.hp = min(p.hp + max(0, p.max_hp - before), p.max_hp)

    def _take_use(self, index: int) -> ItemUsed:
        one = remove_one(self.player.pack, index)
        return ItemUsed(one.id, self.data.items.name(one.id), one.charge)

    def _use_item(self, index: int) -> list[Event]:
        p = self.player
        if not 0 <= index < len(p.pack):
            return [Refused("no_item")]
        d = self.data.items.consumables.get(p.pack[index].id)
        if d is None:
            return [Refused("not_usable")]
        if d.effect == "light":
            return [Refused("already_lit")] if self.torch_lit else self._toggle_torch()
        now = p.ready_at
        events: list[Event] = []
        if d.effect == "heal":
            if p.hp >= p.max_hp:
                return [Refused("full_hp")]
            amount = min(d.value, p.max_hp - p.hp)
            p.hp += amount
            events.append(Healed(amount))
        events.append(self._take_use(index))
        self._spend(self.play.use_cost)
        if d.effect == "status":
            apply_status(p, d.status, now, self.data.statuses, duration=d.value)
        return events

    # -- the torch -----------------------------------------------------------------------

    def _toggle_torch(self) -> list[Event]:
        """Light the torch in hand (a partly burned one relights free), or snuff it. A fresh
        torch comes out of the pack and is billed at its use charge when first lit."""
        p = self.player
        if self.torch_lit:
            self.torch_lit = False
            self._spend(self.play.use_cost)
            self._look()
            return [TorchChanged(False)]
        events: list[Event] = []
        if p.torch_left <= 0:
            slot = next((i for i, it in enumerate(p.pack) if it.id == TORCH), None)
            if slot is None:
                return [Refused("no_torch")]
            events.append(self._take_use(slot))
            p.torch_left = self.data.items.consumables[TORCH].value
        self.torch_lit = True
        self._spend(self.play.use_cost)
        self._look()
        return [*events, TorchChanged(True)]

    def _lose_torch(self) -> Event:
        """The lit torch is gone for good (Brine, or knocked from your hand)."""
        self.torch_lit = False
        self.player.torch_left = 0
        self._look()
        return TorchDropped()

    def _burn(self, elapsed: int) -> list[Event]:
        """A lit torch burns for 400 turns in all, however many times it is snuffed."""
        p = self.player
        if not self.torch_lit:
            return []
        p.torch_left -= elapsed
        if p.torch_left > 0:
            return []
        p.torch_left, self.torch_lit = 0, False
        self._look()
        return [TorchBurnedOut()]

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
        return events + self.noise(self.pos, self._blow_noise())

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
        if m.faction == "undead" and is_active(p, "detergent", now):
            bonus += c.detergent_bonus
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
            return [*events, *self._slain(m, now)]
        if result.outcome is Outcome.CRIT and stats.stuns:
            if apply_status(m, "stunned", now, self.data.statuses):
                events.append(StatusApplied(m.id, m.name, "stunned"))
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
            events += self.noise(p.pos, self._blow_noise())
        else:  # dual_strike: both hands at full attack against the first enemy clockwise
            m = targets[0]
            p.facing = direction_to(p.pos, m.pos)
            events += self._strike(m, main, bonus=value)
            off = offhand_stats(p, self.data, penalty=0)
            if off is not None and m in self.monsters:
                events += self._strike(m, off, bonus=value)
            self._spend(main.attack_cost)
            events += self.noise(p.pos, self._blow_noise())
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
        events += self._land_drops()
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
                events += self._slain(m, now)
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

    def can_lay_trap(self, pos: Pos) -> bool:
        """Only where the level stays whole: no hidden trap may be the only way on, because only
        a Rogue can disarm one. Every trap still live counts as a wall."""
        blocked = {t.pos for t in self.traps if not t.disarmed} | {pos}
        everything = self.grid.count_reachable(self.spec.entry)
        return self.grid.count_reachable(self.spec.entry, blocked) == everything - len(blocked)

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
            events.append(self._lose_torch())  # knocked from your hand
        return events + self._hurt_player(result.damage, m.name)

    def _wear_armor(self, crit: bool) -> list[Event]:
        before = self.player.body_dur
        if before <= 0:
            return []
        after = max(0, before - (2 if crit else 1))
        self.player.body_dur = after
        armor = self.data.items.armor[self.player.body]
        most = armor_max(self.data, self.player, self.player.body)
        return [ArmorDamaged(armor.name, after, most, after == 0)]

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


def _fields(item: LootItem) -> tuple[str, int, int, int, int]:
    """A generated find as the arguments of a pack Item."""
    return (item.id, item.qty, item.charge, item.dur, item.text)


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
