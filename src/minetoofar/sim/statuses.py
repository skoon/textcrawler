"""The status engine (GDD 7.5): data-driven effects with a duration, a delay, and an immunity."""

from collections.abc import Mapping

from minetoofar.content.gamedata import StatusDef
from minetoofar.sim.actors import NEVER, Actor, StatusState

COOLDOWN_PREFIX = "cd:"  # cooldowns are hidden statuses with no data row


def is_active(actor: Actor, status_id: str, now: int) -> bool:
    state = actor.statuses.get(status_id)
    return state is not None and state.ends > now


def apply_status(
    actor: Actor,
    status_id: str,
    now: int,
    defs: Mapping[str, StatusDef],
    duration: int | None = None,
    power: int = 0,
    charges: int = 0,
) -> bool:
    """Apply a status; False if the actor is still immune. Reapplying refreshes, never stacks."""
    d = defs[status_id]
    if actor.immune.get(status_id, 0) > now:
        return False
    length = d.duration_ticks if duration is None else duration
    old = actor.statuses.get(status_id)
    keeps_rhythm = old is not None and old.ends > now and d.tick_ticks > 0
    actor.statuses[status_id] = StatusState(
        ends=now + length if length else NEVER,
        power=power,
        charges=charges,
        next_tick=old.next_tick
        if keeps_rhythm and old
        else (now + d.tick_ticks if d.tick_ticks else 0),
    )
    actor.ready_at += d.delay_ticks
    if d.immune_ticks:
        actor.immune[status_id] = now + length + d.immune_ticks
    return True


def due_ticks(actor: Actor, status_id: str, now: int, defs: Mapping[str, StatusDef]) -> list[int]:
    """The damage of every tick that has come due by `now`, oldest first; ends the status after
    its last tick. Ticks land at fixed times from the moment it was applied."""
    state = actor.statuses.get(status_id)
    if state is None:
        return []
    interval = defs[status_id].tick_ticks
    out: list[int] = []
    while state.next_tick <= now and state.next_tick <= state.ends:
        out.append(state.power)
        state.next_tick += interval
    if now >= state.ends:
        del actor.statuses[status_id]
    return out


def spend_charge(actor: Actor, status_id: str) -> int | None:
    """Use one charge of a charged status; returns its power, or None if there is none to use."""
    state = actor.statuses.get(status_id)
    if state is None or state.charges <= 0:
        return None
    state.charges -= 1
    if state.charges == 0:
        del actor.statuses[status_id]
    return state.power


def start_cooldown(actor: Actor, ability_id: str, now: int, ticks: int) -> None:
    actor.statuses[COOLDOWN_PREFIX + ability_id] = StatusState(ends=now + ticks)


def cooldown_left(actor: Actor, ability_id: str, now: int) -> int:
    state = actor.statuses.get(COOLDOWN_PREFIX + ability_id)
    return max(0, state.ends - now) if state else 0


def effective_cost(actor: Actor, base: int, now: int, defs: Mapping[str, StatusDef]) -> int:
    """An action's cost in ticks after every active status has scaled it (floor each time)."""
    cost = base
    for status_id in actor.statuses:
        if status_id.startswith(COOLDOWN_PREFIX):
            continue
        if is_active(actor, status_id, now):
            cost = cost * defs[status_id].cost_pct // 100
    return cost
