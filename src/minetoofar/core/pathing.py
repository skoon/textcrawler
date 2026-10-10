"""Integer-cost distance maps (octile 10/14). No floats, deterministic tie-breaks."""

import heapq
from collections.abc import Collection

from minetoofar.core.geometry import DIRS8, Pos
from minetoofar.core.grid import Grid, Tile


def distance_map(
    grid: Grid, start: Pos, until: Collection[Pos] = (), only: frozenset[Tile] | None = None
) -> dict[Pos, int]:
    """Cheapest cost from `start` to every reachable tile under Grid.can_step.

    With `until`, the search stops as soon as every one of those tiles has its final cost and
    returns only exact entries (everything at most that costly); a caller that only needs to
    steer a few actors gets the map without paying for the far corners of the level. With `only`,
    every step must land on one of those tile kinds (an Eel's map is brine and nothing else).
    """
    best: dict[Pos, int] = {start: 0}
    heap: list[tuple[int, int, int]] = [(0, start.y, start.x)]
    waiting = set(until)
    stop_cost: int | None = None
    while heap:
        cost, y, x = heapq.heappop(heap)
        here = Pos(x, y)
        if cost > best[here]:
            continue
        waiting.discard(here)
        if until and not waiting:
            stop_cost = cost
            break
        for d in DIRS8:
            if not grid.can_step(here, d):
                continue
            nxt = here.step(d)
            if only is not None and grid.get(nxt.x, nxt.y) not in only:
                continue
            step = (10 if d[0] == 0 or d[1] == 0 else 14) * grid.step_mult(nxt.x, nxt.y)
            if cost + step < best.get(nxt, 1 << 60):
                best[nxt] = cost + step
                heapq.heappush(heap, (cost + step, nxt.y, nxt.x))
    if stop_cost is None:
        return best
    return {p: c for p, c in best.items() if c <= stop_cost}
