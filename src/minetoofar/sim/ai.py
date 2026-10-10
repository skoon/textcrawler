"""Monster decisions (GDD 7.7): who a monster can hit, whether it wakes, and where it steps."""

import heapq
from collections import deque

from minetoofar.core.fov import compute_fov
from minetoofar.core.geometry import DIRS8, Pos, octile
from minetoofar.core.grid import Grid, Tile, is_walkable

WAKE_ADJACENT = (1, 2)
WAKE_NEAR = (1, 6)
NEAR_RADIUS_SQ = 16  # "within 4 tiles", as an integer circle


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


def attack_direction(
    grid: Grid, src: Pos, dst: Pos, phasing: bool = False
) -> tuple[int, int] | None:
    """The step from src onto dst if it is a legal melee reach (no corners, no door diagonals).

    A phasing attacker (a Wraith) or target ignores terrain: walls and corners are no bar."""
    dx, dy = dst.x - src.x, dst.y - src.y
    if max(abs(dx), abs(dy)) != 1:
        return None
    d = (_sign(dx), _sign(dy))
    return d if phasing or grid.can_step(src, d) else None


def wake_odds(src: Pos, target: Pos) -> tuple[int, int] | None:
    """Chance a sleeper stirs on one of its turns, as (numerator, denominator), or None."""
    d2 = (src.x - target.x) ** 2 + (src.y - target.y) ** 2
    if d2 <= 2:
        return WAKE_ADJACENT
    return WAKE_NEAR if d2 <= NEAR_RADIUS_SQ else None


def can_see(grid: Grid, src: Pos, sight: int, target: Pos) -> bool:
    if (src.x - target.x) ** 2 + (src.y - target.y) ** 2 > sight * sight:
        return False
    return target in compute_fov(grid, src, sight)


def next_step(
    grid: Grid, dist: dict[Pos, int], pos: Pos, blocked: set[Pos]
) -> tuple[int, int] | None:
    """Descend the player's distance map; ties go to the earlier direction (N, NE, E, ...)."""
    here = dist.get(pos)
    if here is None:
        return None
    best: tuple[int, int, tuple[int, int]] | None = None
    for index, d in enumerate(DIRS8):
        nxt = pos.step(d)
        if nxt in blocked or not grid.can_step(pos, d) or dist.get(nxt, here) >= here:
            continue
        if best is None or (dist[nxt], index) < (best[0], best[1]):
            best = (dist[nxt], index, d)
    return best[2] if best else None


def noise_reach(grid: Grid, source: Pos, radius: int) -> frozenset[Pos]:
    """Tiles a sound reaches (GDD 7.7): breadth-first through floor, `radius` steps, stopped by
    walls and closed doors, passing open ones."""
    seen = {source}
    frontier = deque([(source, 0)])
    while frontier:
        here, steps = frontier.popleft()
        if steps == radius:
            continue
        for d in DIRS8:
            nxt = here.step(d)
            if nxt in seen or not grid.in_bounds(nxt.x, nxt.y):
                continue
            tile = grid.get(nxt.x, nxt.y)
            if is_walkable(tile) and tile != Tile.DOOR:
                seen.add(nxt)
                frontier.append((nxt, steps + 1))
    return frozenset(seen)


def flee_map(grid: Grid, dist: dict[Pos, int]) -> dict[Pos, int]:
    """The player's distance map negated, then rescanned (GDD 7.7): every tile takes the lowest
    value it can reach by walking, so a fleeing monster is led round corners to open ground
    instead of into the nearest dead end. Lower means safer."""
    flee = {p: -d for p, d in dist.items()}
    heap = [(v, p.y, p.x) for p, v in flee.items()]
    heapq.heapify(heap)
    while heap:
        value, y, x = heapq.heappop(heap)
        here = Pos(x, y)
        if value > flee[here]:
            continue
        for d in DIRS8:
            if not grid.can_step(here, d):
                continue
            nxt = here.step(d)
            cost = (10 if d[0] == 0 or d[1] == 0 else 14) * grid.step_mult(nxt.x, nxt.y)
            if nxt in flee and value + cost < flee[nxt]:
                flee[nxt] = value + cost
                heapq.heappush(heap, (flee[nxt], nxt.y, nxt.x))
    return flee


def flee_step(
    grid: Grid, flee: dict[Pos, int], pos: Pos, blocked: set[Pos]
) -> tuple[int, int] | None:
    """The step that goes most downhill on the flee map, or None when cornered."""
    here = flee.get(pos)
    if here is None:
        return None
    best: tuple[int, int, tuple[int, int]] | None = None
    for index, d in enumerate(DIRS8):
        nxt = pos.step(d)
        if nxt in blocked or not grid.can_step(pos, d) or flee.get(nxt, here) >= here:
            continue
        if best is None or (flee[nxt], index) < (best[0], best[1]):
            best = (flee[nxt], index, d)
    return best[2] if best else None


def phase_step(
    pos: Pos, target: Pos, blocked: set[Pos], bounds: tuple[int, int] | None = None
) -> tuple[int, int] | None:
    """A wall-ignoring step straight toward the target (Wraiths), never onto an occupied tile and,
    given `bounds` (width, height), never off the map."""
    here = octile(pos, target)
    best: tuple[int, int, tuple[int, int]] | None = None
    for index, d in enumerate(DIRS8):
        nxt = pos.step(d)
        score = octile(nxt, target)
        off_map = bounds is not None and not (0 <= nxt.x < bounds[0] and 0 <= nxt.y < bounds[1])
        if nxt in blocked or off_map or score >= here:
            continue
        if best is None or (score, index) < (best[0], best[1]):
            best = (score, index, d)
    return best[2] if best else None
