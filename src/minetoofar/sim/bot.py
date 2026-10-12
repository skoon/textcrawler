"""A deterministic scripted player. The reckless policy hunts every beast and undead it can find,
collects what lies on the floor, then walks to the Down Shaft; the careful one only fights what
is after it, lets sleepers lie, and wears the best gear it finds. Either uses its class ability
whenever one is ready and an enemy is within reach, and drinks a Patch-Up Kit when badly hurt.

It sees the whole map (it is a test and balance tool, not an opponent), so a run is a pure
function of the seed and rank, which is what replay logs and the balance simulator need. It
goes round the traps and open graves it knows about, leaves the Rogue Humans alone unless they
come for it, and never walks into a tile where something unseen is lurking.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from minetoofar.core.fov import compute_fov
from minetoofar.core.geometry import DIRS8, Pos, octile
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.pathing import distance_map
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.events import (
    Command,
    DropItem,
    Equip,
    Event,
    Move,
    Pickup,
    TakeSupply,
    UseAbility,
    UseItem,
    Wait,
)
from minetoofar.sim.game import Game
from minetoofar.sim.items import KIT, carried
from minetoofar.sim.statuses import is_active
from minetoofar.sim.supply import Crate


@dataclass(frozen=True)
class Policy:
    """How the bot plays: who it fights, when it heals, what it wears."""

    name: str
    hunt: str = "all"  # all: every monster it can see; aware: only those already after it
    kit_pct: int = 50  # drink a Patch-Up Kit at this percent of max HP or less
    equip: bool = False  # wear the best gear it finds
    wait_for: int = 0  # let an enemy that is after it come, once it is this close (tiles)
    leave_sleepers: bool = False  # walk round monsters that have not noticed it
    plan_around: bool = False  # find a whole route round hazards instead of stepping greedily
    crates: str = "all"  # all: take every line it has room for; gear: only upgrades
    buffs: bool = False  # drink Overtime Fizz for a Rogue Human, a Detergent Coat for the undead


RECKLESS = Policy("reckless")
CAREFUL = Policy(
    "careful", hunt="aware", kit_pct=50, equip=True, wait_for=3, leave_sleepers=True,
    plan_around=True, crates="gear", buffs=True,
)  # fmt: skip
AWARE = ("hunting", "alerted")  # monsters that know where the player is


Routes = dict[tuple[Pos, frozenset[Pos]], tuple[Grid, dict[Pos, int]]]


@dataclass
class Memory:
    """What the careful policy keeps in mind on one level, so it need not work it out each step."""

    routes: Routes = field(default_factory=dict)  # distances to the goal round the hazards
    graves: frozenset[Pos] | None = None  # open graves never move
    skip: set[Pos] = field(default_factory=set)  # finds there is no way to
    waits: int = 0  # turns in a row spent waiting for a hunter that has not come
    target: Pos | None = None  # the find it is on its way to, so it does not dither


def _graves(game: Game) -> frozenset[Pos]:
    return frozenset(
        Pos(x, y)
        for y in range(game.spec.height)
        for x in range(game.spec.width)
        if game.grid.get(x, y) == Tile.OPEN_GRAVE
    )


def _hazards(game: Game, memory: Memory | None = None) -> set[Pos]:
    """Tiles to go round: traps, open graves, and anything hidden in the way."""
    lurking = {m.pos for m in game.monsters if m.hidden}
    if memory is None:
        graves = _graves(game)
    else:
        if memory.graves is None:
            memory.graves = _graves(game)
        graves = memory.graves
    return lurking | graves | {t.pos for t in game.traps if not t.disarmed}


def _step_toward(game: Game, goal: Pos, avoid: set[Pos]) -> Move | None:
    """The step that descends the distance map from `goal`; stepping onto a monster attacks it."""
    dist = distance_map(game.grid, goal, until=[game.pos])
    here = dist.get(game.pos)
    if here is None:
        return None
    best: tuple[int, int] | None = None
    for index, d in enumerate(DIRS8):
        nxt = game.pos.step(d)
        if nxt in avoid and nxt != goal:
            continue
        if game.grid.can_step(game.pos, d) and dist.get(nxt, here) < here:
            if best is None or (dist[nxt], index) < best:
                best = (dist[nxt], index)
    return Move(*DIRS8[best[1]]) if best else None


def _planned_step(
    game: Game, goal: Pos, avoid: set[Pos], memory: Memory | None = None
) -> Move | None:
    """The first step of a route to `goal` that treats every tile in `avoid` as a wall, or None
    when there is no such route. The distances are kept in `cache` while the goal and the tiles
    to avoid stay the same, which is most of a walk."""
    key = (goal, frozenset(avoid - {game.pos}))
    if memory is not None and key in memory.routes:
        walled, dist = memory.routes[key]
    else:
        walled = Grid(game.spec.width, game.spec.height, game.grid.to_bytes())
        for a in key[1]:
            if a != goal and walled.in_bounds(a.x, a.y):
                walled.set(a.x, a.y, Tile.WALL)
        dist = distance_map(walled, goal)
        if memory is not None:
            memory.routes.clear()
            memory.routes[key] = (walled, dist)
    here = dist.get(game.pos)
    if here is None:
        return None
    best: tuple[int, int] | None = None
    for index, d in enumerate(DIRS8):
        nxt = game.pos.step(d)
        if walled.can_step(game.pos, d) and dist.get(nxt, here) < here:
            if best is None or (dist[nxt], index) < best:
                best = (dist[nxt], index)
    return Move(*DIRS8[best[1]]) if best else None


def _wanted(game: Game, item_id: str, qty: int) -> bool:
    """Worth the walk: anything but a consumable the pack has no room left for."""
    stock = game.data.items.consumables.get(item_id)
    return stock is None or carried(game.player.pack, item_id) + qty <= stock.carry


def _crate_picks(game: Game, crate: Crate, policy: Policy = RECKLESS) -> tuple[int, ...]:
    """The lines of a crate worth taking: all the pack has room for (stock counted as it would
    be taken), or with the `gear` policy only the equipment that beats what is worn."""
    room = {k: carried(game.player.pack, k) for k in game.data.items.consumables}
    picks = []
    for i, line in enumerate(crate.lines):
        if policy.crates == "gear" and not _is_upgrade(game, line.item, line.dur):
            continue
        stock = game.data.items.consumables.get(line.item)
        if stock is not None:
            if room[line.item] + line.qty > stock.carry:
                continue
            room[line.item] += line.qty
        picks.append(i)
    return tuple(picks)


def _nearest_find(
    game: Game, policy: Policy = RECKLESS, memory: Memory | None = None
) -> Pos | None:
    """The closest find on the floor, or crate with something in it, to take. The reckless bot
    asks the distance map; the careful one goes by the crow and gives up on what it cannot reach."""
    if memory is not None:
        spots = [f.pos for f in _on_top(game) if _worth_taking(game, f.item, policy)]
        spots += [c.pos for c in game.crates if _crate_picks(game, c, policy)]
        shunned = memory.skip | (_sleepers_reach(game) if policy.leave_sleepers else set())
        spots = [q for q in spots if q not in shunned]
        if memory.target in spots:
            return memory.target
        memory.target = min(spots, key=lambda q: (octile(game.pos, q), q.y, q.x), default=None)
        return memory.target
    dist = distance_map(game.grid, game.pos)
    wanted = [f.pos for f in game.floor if f.pos in dist and _wanted(game, f.item.id, f.item.qty)]
    wanted += [c.pos for c in game.crates if c.pos in dist and _crate_picks(game, c, policy)]
    return min(wanted, key=lambda p: (dist[p], p.y, p.x), default=None)


def _is_gear(game: Game, item_id: str) -> bool:
    items = game.data.items
    return (
        item_id in items.weapons
        or item_id in items.armor
        or item_id in items.hats
        or (item_id in items.shields)
    )


def _grab(game: Game, f: FloorItem, policy: Policy, memory: Memory | None) -> bool:
    """Is `f`, lying where we stand, what a pick-up would take and want to take?"""
    if memory is None:
        return _wanted(game, f.item.id, f.item.qty)
    return f in _on_top(game) and _worth_taking(game, f.item, policy)


def _on_top(game: Game) -> list[FloorItem]:
    """What a pick-up would take at each spot: only the item on top of a pile."""
    top: dict[Pos, FloorItem] = {}
    for f in game.floor:
        top.setdefault(f.pos, f)
    return list(top.values())


def _worth_taking(game: Game, item: Item, policy: Policy) -> bool:
    """Gear that would not be worn only fills the pack."""
    if policy.equip and _is_gear(game, item.id):
        return _is_upgrade(game, item.id, item.dur)
    return _wanted(game, item.id, item.qty)


def _junk(game: Game) -> DropItem | None:
    """A spare piece of gear in the pack, now that something better is worn."""
    for i, it in enumerate(game.player.pack):
        if _is_gear(game, it.id) and not _is_upgrade(game, it.id, it.dur):
            return DropItem(i)
    return None


def _prey(game: Game, policy: Policy) -> list[Pos]:
    return [
        m.pos
        for m in game.monsters
        if not m.hidden and m.faction != "human" and (policy.hunt == "all" or m.state in AWARE)
    ]


WAIT_LIMIT = 6  # turns: a hunter that has not come by then is stuck behind something


def choose(game: Game, policy: Policy = RECKLESS, memory: Memory | None = None) -> Command | None:
    """The next command, or None when the run is over (dead, or standing on the Down Shaft)."""
    command = _choose(game, policy, memory)
    if memory is not None:
        memory.waits = memory.waits + 1 if isinstance(command, Wait) else 0
    return command


def _choose(game: Game, policy: Policy, memory: Memory | None) -> Command | None:
    if game.dead:
        return None
    p = game.player
    if p.hp * 100 <= policy.kit_pct * p.max_hp and p.hp + 10 <= p.max_hp:
        kit = next((i for i, it in enumerate(p.pack) if it.id == KIT), None)
        if kit is not None:
            return UseItem(kit)
    if policy.buffs and (buff := _buff(game)) is not None:
        return buff
    beside = game.adjacent_enemies()
    if beside:  # whoever is on top of us gets dealt with first, humans included
        if game.view().hero.ability.ready:
            return UseAbility()  # Cleave, a fresh coat of poison, or Dual Strike
        weakest = min(beside, key=lambda m: (m.hp, m.id))
        return Move(weakest.pos.x - game.pos.x, weakest.pos.y - game.pos.y)
    if policy.equip and (upgrade := best_upgrade(game)) is not None:
        return upgrade
    if policy.equip and (junk := _junk(game)) is not None:
        return junk
    finding = False
    prey = _prey(game, policy)
    patient = memory is None or memory.waits < WAIT_LIMIT
    if prey and policy.wait_for and patient and _closest(game, prey) <= policy.wait_for:
        return Wait()  # it is coming: take it here rather than walk into whatever is behind
    if prey:
        goal = min(prey, key=lambda p: (octile(game.pos, p), p.y, p.x))
    elif any(f.pos == game.pos and _grab(game, f, policy, memory) for f in game.floor):
        return Pickup()
    elif (crate := game.crate_here()) is not None and (picks := _crate_picks(game, crate, policy)):
        return TakeSupply(picks)
    elif (find := _nearest_find(game, policy, memory)) is not None:
        goal, finding = find, True
    elif game.pos != game.spec.exit:
        goal = game.spec.exit
    else:
        return None
    avoid = _hazards(game, memory)

    def stepper(goal: Pos, avoid: set[Pos]) -> Move | None:
        if policy.plan_around:
            return _planned_step(game, goal, avoid, memory)
        return _step_toward(game, goal, avoid)

    if policy.leave_sleepers:
        step = stepper(goal, avoid | _sleepers_reach(game))
        if step is not None:
            return step
        if finding and memory is not None:
            memory.skip.add(goal)  # not worth waking anyone for: do without it
            return _choose(game, policy, memory)
        step = stepper(goal, avoid | _sleepers_reach(game, bosses_only=True))
        if step is not None:
            return step  # past the small fry then, but never past the boss
    careful = stepper(goal, avoid)
    if careful is not None:
        return careful
    lurking = {m.pos for m in game.monsters if m.hidden}
    risky = _step_toward(game, goal, lurking)  # no safe way: take the risk
    if risky is None and memory is not None:
        memory.skip.add(goal)  # nowhere to go for now: give that one up and think again
        return Wait()
    return risky


BUFFS = (("human", "overtime_fizz", "overtime"), ("undead", "sanctified_detergent", "detergent"))
BOSS_RANGE = 12  # tiles: a Rogue Human this near is met at full strength
BOSS_HP_PCT = 80
BUFF_RANGE = 6  # tiles: close enough that the fight is coming, far enough to drink first


def _buff(game: Game) -> UseItem | None:
    """Drink what helps against the enemy that is after us, once, before it arrives."""
    p = game.player
    boss_near = any(
        m.faction == "human" and not m.hidden
        and max(abs(m.pos.x - game.pos.x), abs(m.pos.y - game.pos.y)) <= BOSS_RANGE
        for m in game.monsters
    )  # fmt: skip
    if boss_near and p.hp * 100 < BOSS_HP_PCT * p.max_hp and p.hp + 10 <= p.max_hp:
        kit = next((i for i, it in enumerate(p.pack) if it.id == KIT), None)
        if kit is not None:
            return UseItem(kit)  # never meet a boss half-healed
    for faction, item_id, status in BUFFS:
        coming = any(
            m.faction == faction and m.state in AWARE and not m.hidden
            and max(abs(m.pos.x - game.pos.x), abs(m.pos.y - game.pos.y)) <= BUFF_RANGE
            for m in game.monsters
        )  # fmt: skip
        if coming and not is_active(p, status, p.ready_at):
            slot = next((i for i, it in enumerate(p.pack) if it.id == item_id), None)
            if slot is not None:
                return UseItem(slot)
    return None


def _closest(game: Game, spots: list[Pos]) -> int:
    return min(max(abs(p.x - game.pos.x), abs(p.y - game.pos.y)) for p in spots)


def _sleepers_reach(game: Game, bosses_only: bool = False) -> set[Pos]:
    """The tiles beside monsters that have not noticed the player: not worth waking them for.
    With `bosses_only`, just the Rogue Humans' sight, which is never worth risking."""
    near: set[Pos] = set()
    for m in game.monsters:
        if m.state in AWARE or m.hidden or (bosses_only and m.faction != "human"):
            continue
        if m.faction == "human":  # a Rogue Human is a boss: stay out of his sight altogether
            near |= compute_fov(game.grid, m.pos, m.sight)
        else:
            near |= {m.pos.step(d) for d in DIRS8}
    return near


# -- wearing what is found -----------------------------------------------------------------------


def _armor_score(game: Game, armor_id: str, dur: int) -> int:
    a = game.data.items.armor[armor_id]
    return 0 if dur <= 0 else 4 * a.dr + 3 * a.defense


def _weapon_score(game: Game, weapon_id: str) -> int:
    w = game.data.items.weapons[weapon_id]
    if w.two_handed:
        return 0  # it would cost the shield; not worth the bother
    swing = w.dice_n * (w.dice_sides + 1) + 2 * w.dmg + 3 * w.atk
    return swing * 100 // w.cost


def _is_upgrade(game: Game, item_id: str, dur: int) -> bool:
    """Would wearing this beat what is worn in its slot?"""
    p, items = game.player, game.data.items
    if item_id in items.consumables or item_id in items.valuables:
        return False
    kind = items.category(item_id)
    if kind == "armor":
        sound = dur * 2 >= items.armor[item_id].dur
        return sound and _armor_score(game, item_id, dur) > _armor_score(game, p.body, p.body_dur)
    if kind == "hat":
        return items.hats[item_id].defense > items.hats[p.head].defense
    if kind == "shield":
        now = items.shields[p.offhand].defense if p.offhand in items.shields else -1
        wanted = p.offhand == "" or p.offhand in items.shields
        return (
            wanted
            and items.shields[item_id].defense > now
            and not items.weapons[p.weapon].two_handed
        )
    if kind == "weapon":
        return _weapon_score(game, item_id) > _weapon_score(game, p.weapon)
    return kind == "trinket" and not p.trinket and item_id != "laminated_lanyard"


def best_upgrade(game: Game) -> Equip | None:
    """An Equip command for the first pack item that beats what is worn in its slot."""
    for i, it in enumerate(game.player.pack):
        if _is_upgrade(game, it.id, it.dur):
            return Equip(i)
    return None


def play(
    game: Game, submit: Callable[[Command], list[Event]], limit: int, policy: Policy = RECKLESS
) -> int:
    """Play until the run ends or `limit` commands; returns how many were sent."""
    sent = 0
    memory = Memory()
    while sent < limit and (command := choose(game, policy, memory)) is not None:
        submit(command)
        sent += 1
    return sent
