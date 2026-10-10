"""Small questions about the rooms of a generated level, shared by every generation stage."""

from collections.abc import Collection, Sequence

from minetoofar.core.geometry import DIRS8, Pos
from minetoofar.core.grid import Grid, Tile
from minetoofar.gen.level_spec import Room

_PLAIN = (Tile.FLOOR, Tile.CAVE_FLOOR)


def floor_tiles(grid: Grid, room: Room) -> list[Pos]:
    """The plain floor of a room, row by row (stairs, doors, and props are not plain floor)."""
    return [
        Pos(x, y)
        for y in range(room.y, room.y + room.h)
        for x in range(room.x, room.x + room.w)
        if grid.get(x, y) in _PLAIN
    ]


def interior_tiles(grid: Grid, room: Room) -> list[Pos]:
    """Floor tiles whose eight neighbours are all plain floor: nothing there blocks a doorway or
    hugs a wall, so Brine, gravestones, and tombs go here and a walkable ring is always left."""
    return [
        p
        for p in floor_tiles(grid, room)
        if all(
            grid.in_bounds(p.x + dx, p.y + dy) and grid.get(p.x + dx, p.y + dy) in _PLAIN
            for dx, dy in DIRS8
        )
    ]


def flood_candidates(
    grid: Grid, rooms: Sequence[Room], skip: Collection[int], min_pct: int
) -> list[Room]:
    """Rooms (other than those in `skip`) whose interior is at least `min_pct` percent of their
    floor: the only ones that can be a Flooded Gallery (GDD 9.3)."""
    found = []
    for r in rooms:
        if r.id in skip:
            continue
        inner, floor = len(interior_tiles(grid, r)), len(floor_tiles(grid, r))
        if inner and inner * 100 >= min_pct * floor:
            found.append(r)
    return found


def room_containing(rooms: Sequence[Room], pos: Pos) -> Room | None:
    return next((r for r in rooms if r.x <= pos.x < r.x + r.w and r.y <= pos.y < r.y + r.h), None)
