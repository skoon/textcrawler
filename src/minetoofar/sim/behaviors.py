"""What each kind of monster does on its turn (GDD 7.6, 7.7).

Every brain starts the same way: asleep monsters roll to wake, idle ones look for the player,
alerted ones walk toward a sound. Once a monster is hunting, the kind decides what it does:
Miners, Skeletons, and Vermin close in and strike; Wraiths phase through walls; Eels lurk in the
Brine; Badgers run when hurt; Grimsby hangs back behind his undead; Vane lays traps and retreats.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from minetoofar.core.geometry import Pos, direction_to
from minetoofar.core.grid import Tile
from minetoofar.core.pathing import distance_map
from minetoofar.sim import ai
from minetoofar.sim.actors import Monster
from minetoofar.sim.events import (
    Attacked,
    Burrowed,
    DoorOpened,
    Event,
    Fled,
    Noticed,
    Rose,
    StatusApplied,
    Surfaced,
)
from minetoofar.sim.statuses import apply_status

if TYPE_CHECKING:
    from minetoofar.sim.game import Game

Handler = Callable[["Game", Monster, int], list[Event]]


def take_turn(game: "Game", m: Monster) -> list[Event]:
    """One action by `m`, at the moment its clock says it is due."""
    now = m.ready_at
    events = game.collect_poison(m, now)
    if m not in game.monsters:
        return events  # the poison finished it
    return events + _HANDLERS[m.behavior](game, m, now)


# -- shared pieces -------------------------------------------------------------------------------


def _dist_sq(a: Pos, b: Pos) -> int:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def _chebyshev(a: Pos, b: Pos) -> int:
    return max(abs(a.x - b.x), abs(a.y - b.y))


def _sees(game: "Game", m: Monster) -> bool:
    if m.behavior == "phaser":  # a Wraith's sight ignores walls
        return _dist_sq(m.pos, game.pos) <= m.sight * m.sight
    return ai.can_see(game.grid, m.pos, m.sight, game.pos)


def _wait(game: "Game", m: Monster, now: int) -> None:
    game.spend_monster(m, game.play.wait_cost, now)


def _notice(game: "Game", m: Monster, now: int) -> list[Event]:
    m.state, m.alert_pos = "hunting", None
    return [Noticed(m.id, m.name), *game.speak(m, "on_sight", now)]


def _stir(game: "Game", m: Monster, now: int) -> tuple[list[Event], bool]:
    """The states before the chase. Returns the events and whether the turn is used up; a
    monster that has just noticed the player goes on to act in the same turn."""
    if m.state == "asleep":
        events: list[Event] = []
        odds = ai.wake_odds(m.pos, game.pos)
        if odds and game.rng.chance(*odds):
            events = _notice(game, m, now)
        _wait(game, m, now)
        return events, True
    if m.state == "buried":
        events = []
        if _dist_sq(m.pos, game.pos) <= game.ai.buried_rise_radius_sq:
            m.state = "hunting"
            events = [Rose(m.id, m.name)]
        _wait(game, m, now)
        return events, True
    if m.state in ("idle", "alerted"):
        if _sees(game, m):
            return _notice(game, m, now), False
        if m.state == "idle":
            _wait(game, m, now)
            return [], True
        return _walk_to_noise(game, m, now), True
    return [], False


def _walk_to_noise(game: "Game", m: Monster, now: int) -> list[Event]:
    target = m.alert_pos
    step = None
    if target is not None and target != m.pos:
        if m.behavior == "phaser":
            step = ai.phase_step(
                m.pos, target, game.occupied(m), (game.spec.width, game.spec.height)
            )
        else:
            dist = distance_map(game.grid, target, until=[m.pos])
            step = ai.next_step(game.grid, dist, m.pos, game.occupied(m))
    if step is None:  # arrived, or no way there: nothing to see here
        m.state, m.alert_pos = "idle", None
        _wait(game, m, now)
        return []
    return _step(game, m, now, step)


def _step(
    game: "Game", m: Monster, now: int, step: tuple[int, int], noisy: bool = False
) -> list[Event]:
    """Move one tile. Closed doors are bumped open first, Rubble costs double, a Skeleton clangs."""
    dest = m.pos.step(step)
    m.facing = step
    phasing = m.behavior == "phaser"
    cost = m.move_cost * (1 if phasing else game.grid.step_mult(dest.x, dest.y))
    game.spend_monster(m, cost, now)
    events: list[Event] = []
    if not phasing and game.grid.get(dest.x, dest.y) == Tile.DOOR:
        game.grid.set(dest.x, dest.y, Tile.DOOR_OPEN)
        events += [DoorOpened(dest, by=m.id), *game.noise(dest, game.noises.door)]
    else:
        m.pos = dest
    if noisy:
        events += game.noise(m.pos, game.noises.clang)
    return events


def _swarm_bonus(game: "Game", m: Monster) -> int:
    """Vermin: +1 ATK for each other Vermin beside the player, up to the cap."""
    if m.behavior != "swarm":
        return 0
    others = sum(
        1
        for o in game.monsters
        if o is not m and o.kind == m.kind and _chebyshev(o.pos, game.pos) <= 1
    )
    return min(game.ai.swarm_max, others)


def _attack(
    game: "Game", m: Monster, now: int, situational: int = 0, noisy: bool = False
) -> list[Event]:
    m.facing = direction_to(m.pos, game.pos)
    events = game.attack_player(m, situational)
    swing = next(e for e in events if isinstance(e, Attacked))
    if not game.dead:
        events += _after_swing(game, m, swing, now)
    game.spend_monster(m, m.stats.attack_cost, now)
    if noisy:
        events += game.noise(m.pos, game.noises.clang)
    return events


def _after_swing(game: "Game", m: Monster, swing: Attacked, now: int) -> list[Event]:
    """What a particular blow does besides hurt: a Skeleton's natural 20 stuns, a Wraith's hit
    may Clock you In, and a human can't help commenting."""
    events: list[Event] = []
    statuses = game.data.statuses
    if m.behavior == "skeleton" and swing.roll == 20:
        if apply_status(game.player, "stunned", now, statuses):
            events.append(StatusApplied(0, game.player.name, "stunned"))
    if (
        m.behavior == "phaser"
        and swing.damage > 0
        and game.player.immune.get("clocked_in", 0) <= now
    ):
        if game.rng.chance(game.ai.clock_in_pct, 100):
            apply_status(game.player, "clocked_in", now, statuses)
            events.append(StatusApplied(0, game.player.name, "clocked_in"))
    if swing.damage > 0:
        events += game.speak(m, "on_hit", now)
    return events


def _hunt(game: "Game", m: Monster, now: int, noisy: bool = False) -> list[Event]:
    """Strike if the player is in reach; otherwise step down the player's distance map."""
    if ai.attack_direction(game.grid, m.pos, game.pos) is not None:
        return _attack(game, m, now, _swarm_bonus(game, m), noisy)
    step = ai.next_step(game.grid, game.distances_for(m), m.pos, game.occupied(m))
    if step is None:
        _wait(game, m, now)
        return []
    return _step(game, m, now, step, noisy)


def _flee(game: "Game", m: Monster, now: int) -> list[Event]:
    """One step down the flee map; a cornered monster fights if it can."""
    step = ai.flee_step(game.grid, game.flee_map(), m.pos, game.occupied(m))
    if step is not None:
        return _step(game, m, now, step)
    if ai.attack_direction(game.grid, m.pos, game.pos) is not None:
        return _attack(game, m, now)
    _wait(game, m, now)
    return []


# -- the brains --------------------------------------------------------------------------------


def _hunter(game: "Game", m: Monster, now: int) -> list[Event]:
    """Shambling Miners and Cave Vermin; Skeletons are the same, but loud."""
    events, done = _stir(game, m, now)
    if done:
        return events
    return events + _hunt(game, m, now, noisy=m.behavior == "skeleton")


def _phaser(game: "Game", m: Monster, now: int) -> list[Event]:
    """Timecard Wraith: moves through walls at one tile a turn, never onto another actor."""
    events, done = _stir(game, m, now)
    if done:
        return events
    if ai.attack_direction(game.grid, m.pos, game.pos, phasing=True) is not None:
        return events + _attack(game, m, now)
    step = ai.phase_step(m.pos, game.pos, game.occupied(m), (game.spec.width, game.spec.height))
    if step is None:
        _wait(game, m, now)
        return events
    return events + _step(game, m, now, step)


def _eel(game: "Game", m: Monster, now: int) -> list[Event]:
    """Blind Ore-Eel: waits submerged, ambushes whoever comes beside it, never leaves the Brine."""
    beside = ai.attack_direction(game.grid, m.pos, game.pos) is not None
    if m.state == "submerged":
        if not beside:
            _wait(game, m, now)
            return []
        bonus = 0 if game.is_tracker else game.ai.eel_ambush_bonus
        m.state, m.since = "hunting", now
        return [Surfaced(m.id, m.name), *_attack(game, m, now, bonus)]
    if beside:
        m.since = now
        return _attack(game, m, now)
    if now - m.since >= game.ai.eel_resubmerge_ticks:
        m.state = "submerged"
        _wait(game, m, now)
        return []
    if _dist_sq(m.pos, game.pos) <= m.sight * m.sight:
        dist = distance_map(game.grid, game.pos, until=[m.pos], only=frozenset({Tile.BRINE}))
        step = ai.next_step(game.grid, dist, m.pos, game.occupied(m))
        if step is not None:
            return _step(game, m, now, step)
    _wait(game, m, now)
    return []


def _badger(game: "Game", m: Monster, now: int) -> list[Event]:
    """Gem Badger: fights until it is down to 40% health, then runs, and burrows if it gets away."""
    if m.state != "fleeing":
        events, done = _stir(game, m, now)
        if done:
            return events
        if m.hp * 100 > m.max_hp * game.ai.badger_flee_pct:
            return events + _hunt(game, m, now)
        m.state, m.unseen_since = "fleeing", None
        events.append(Fled(m.id, m.name))
    else:
        events = []
    if game.visible(m):
        m.unseen_since = None
    elif m.unseen_since is None:
        m.unseen_since = now
    elif now - m.unseen_since >= game.ai.badger_burrow_ticks:
        game.remove(m)
        return events + [Burrowed(m.id, m.name)]
    return events + _flee(game, m, now)


def _overseer(game: "Game", m: Monster, now: int) -> list[Event]:
    """Foreman Grimsby: speeds his undead, and holds back two or three tiles while they fight."""
    events, done = _stir(game, m, now)
    if done:
        return events
    limit = game.ai.aura_radius_sq
    entourage = [
        o
        for o in game.monsters
        if o is not m and o.faction == "undead" and _dist_sq(o.pos, m.pos) <= limit
    ]
    for o in entourage:
        apply_status(o, "overtime", now, game.data.statuses, duration=game.ai.aura_ticks)
    if not entourage:
        return events + _hunt(game, m, now)  # nobody left to hide behind
    gap = _chebyshev(m.pos, game.pos)
    if gap < game.ai.overseer_min:
        return events + _flee(game, m, now)
    if gap > game.ai.overseer_max:
        return events + _hunt(game, m, now)
    _wait(game, m, now)
    return events


def _trapper(game: "Game", m: Monster, now: int) -> list[Event]:
    """Prospector Vane: lays a hidden trap where he stands (never where it would be the only way
    on), then retreats before returning."""
    if m.state == "fleeing":
        if now - m.since < game.ai.trapper_flee_ticks:
            return _flee(game, m, now)
        m.state = "hunting"
    events, done = _stir(game, m, now)
    if done:
        return events
    ready = m.traps_left > 0 and now - m.last_trap >= game.ai.trap_interval_ticks
    in_view = _dist_sq(m.pos, game.pos) <= game.ai.trap_sight_sq and _sees(game, m)
    if ready and in_view and game.can_lay_trap(m.pos):
        game.lay_trap(m.pos)
        m.traps_left -= 1
        m.last_trap, m.state, m.since = now, "fleeing", now
        _wait(game, m, now)
        return events + game.speak(m, "on_flee", now)
    return events + _hunt(game, m, now)


_HANDLERS: dict[str, Handler] = {
    "hunter": _hunter,
    "swarm": _hunter,
    "skeleton": _hunter,
    "phaser": _phaser,
    "eel": _eel,
    "badger": _badger,
    "overseer": _overseer,
    "trapper": _trapper,
}
