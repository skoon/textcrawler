import pytest

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Grid
from minetoofar.core.seed import Seed
from minetoofar.gen.layout import generate_level
from minetoofar.gen.level_spec import Room
from minetoofar.gen.rooms import (
    flood_candidates,
    floor_tiles,
    interior_tiles,
    room_containing,
)
from tests.helpers import grid_from_rows


def room(x: int, y: int, w: int, h: int, rid: int = 0, cave: bool = False) -> Room:
    return Room(rid, x, y, w, h, cave, Pos(x + w // 2, y + h // 2))


FIVE = ["#######", "#.....#", "#.....#", "#.....#", "#.....#", "#.....#", "#######"]


def test_a_five_by_five_room_has_a_three_by_three_interior() -> None:
    g = grid_from_rows(FIVE)
    r = room(1, 1, 5, 5)
    assert len(floor_tiles(g, r)) == 25
    assert interior_tiles(g, r) == [Pos(x, y) for y in (2, 3, 4) for x in (2, 3, 4)]


def test_floor_tiles_skip_stairs_doors_and_walls() -> None:
    g = grid_from_rows(["#####", "#<..+", "#####"])
    r = room(1, 1, 4, 1)
    assert floor_tiles(g, r) == [Pos(2, 1), Pos(3, 1)]


def test_a_tile_beside_a_door_or_corridor_mouth_is_not_interior() -> None:
    rows = ["#######", "#.....#", "#.....#", "#.....#", "#.....#", "#.....#", "###+###"]
    g = grid_from_rows(rows)
    inner = interior_tiles(g, room(1, 1, 5, 5))
    assert (
        Pos(3, 5) not in inner and Pos(2, 5) not in inner
    )  # the bottom row touches the door's wall


def test_every_rectangular_room_can_be_flooded() -> None:
    g = grid_from_rows(FIVE)
    assert flood_candidates(g, [room(1, 1, 5, 5)], set(), 30) == [room(1, 1, 5, 5)]


def test_a_thin_room_cannot_and_skipped_rooms_do_not_count() -> None:
    g = grid_from_rows(["#########", "#.......#", "#.......#", "#########"])
    assert flood_candidates(g, [room(1, 1, 7, 2)], set(), 30) == []
    g2 = grid_from_rows(FIVE)
    assert flood_candidates(g2, [room(1, 1, 5, 5)], {0}, 30) == []


def test_the_percentage_is_of_the_rooms_floor() -> None:
    g = grid_from_rows(FIVE)  # 9 of 25 is 36%
    assert flood_candidates(g, [room(1, 1, 5, 5)], set(), 36) != []
    assert flood_candidates(g, [room(1, 1, 5, 5)], set(), 37) == []


def test_room_containing_finds_the_room_a_tile_is_in() -> None:
    rooms = [room(1, 1, 5, 5, 0), room(10, 1, 5, 5, 1)]
    assert room_containing(rooms, Pos(11, 2)) == rooms[1]
    assert room_containing(rooms, Pos(8, 2)) is None


@pytest.mark.parametrize("seed", ["BRASSLAMP42", "GOLD0001", "GOLD0042"])
def test_generated_levels_always_leave_room_for_the_required_flooded_galleries(seed: str) -> None:
    need = load_balance().features
    for level in range(1, LEVELS + 1):
        spec = generate_level(Seed.parse(seed), level)
        grid = Grid(spec.width, spec.height, spec.tiles)
        skip = {
            r.id
            for r in spec.rooms
            if room_containing([r], spec.entry) or room_containing([r], spec.exit)
        }
        wanted = need.level3_flooded_min if level == 3 else 1
        assert len(flood_candidates(grid, list(spec.rooms), skip, need.flood_min_pct)) >= wanted
