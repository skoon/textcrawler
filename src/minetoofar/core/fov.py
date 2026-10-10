"""Integer symmetric shadowcasting (Albert Ford's algorithm) with a circular radius.

Each quadrant is scanned row by row away from the origin. A row is a depth plus a pair of
slopes; slopes are exact integer fractions (num, den) so no float ever touches visibility.
Floor tiles are visible only when their centre lies inside the slope range, which is what makes
sight symmetric between floor tiles. Wall tiles are revealed whenever the scan touches them.
"""

from collections.abc import Callable

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Grid, blocks_sight

Slope = tuple[int, int]  # numerator, denominator (> 0)

# (row, col) -> (dx, dy) for north, east, south, west
_QUADRANTS: tuple[Callable[[int, int], tuple[int, int]], ...] = (
    lambda row, col: (col, -row),
    lambda row, col: (row, col),
    lambda row, col: (col, row),
    lambda row, col: (-row, col),
)


def _ties_up(depth: int, slope: Slope) -> int:
    """floor(depth * slope + 1/2)"""
    num, den = slope
    return (2 * depth * num + den) // (2 * den)


def _ties_down(depth: int, slope: Slope) -> int:
    """ceil(depth * slope - 1/2)"""
    num, den = slope
    return -((den - 2 * depth * num) // (2 * den))


def _tile_slope(depth: int, col: int) -> Slope:
    return (2 * col - 1, 2 * depth)


def _scan_quadrant(
    grid: Grid,
    origin: Pos,
    radius: int,
    to_world: Callable[[int, int], tuple[int, int]],
    seen: set[Pos],
) -> None:
    limit = radius * radius

    def scan(depth: int, start: Slope, end: Slope) -> None:
        if depth > radius:
            return
        prev_wall: bool | None = None
        for col in range(_ties_up(depth, start), _ties_down(depth, end) + 1):
            dx, dy = to_world(depth, col)
            tile = Pos(origin.x + dx, origin.y + dy)
            in_bounds = grid.in_bounds(tile.x, tile.y)
            wall = not in_bounds or blocks_sight(grid.get(tile.x, tile.y))
            # the tile centre lies inside the cone: depth*start <= col <= depth*end
            centred = col * start[1] >= depth * start[0] and col * end[1] <= depth * end[0]
            if in_bounds and col * col + depth * depth <= limit and (wall or centred):
                seen.add(tile)
            if prev_wall and not wall:
                start = _tile_slope(depth, col)
            if prev_wall is False and wall:
                scan(depth + 1, start, _tile_slope(depth, col))
            prev_wall = wall
        if prev_wall is False:
            scan(depth + 1, start, end)

    scan(1, (-1, 1), (1, 1))


def compute_fov(grid: Grid, origin: Pos, radius: int) -> frozenset[Pos]:
    """Every tile within `radius` (Euclidean, integer) that the origin can see, walls included."""
    if radius < 0:
        raise ValueError("radius must not be negative")
    seen = {origin}
    for to_world in _QUADRANTS:
        _scan_quadrant(grid, origin, radius, to_world, seen)
    return frozenset(seen)
