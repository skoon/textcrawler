import pytest

from minetoofar.core.fov import compute_fov
from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Grid, blocks_sight
from minetoofar.core.seed import Seed
from minetoofar.gen.layout import generate_level
from tests.helpers import grid_from_rows


def seen_art(rows: list[str], radius: int) -> list[str]:
    """Render the visible tiles of `rows` from its '@'; everything not visible becomes a space."""
    origin = next(Pos(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == "@")
    grid = grid_from_rows([row.replace("@", ".") for row in rows])
    visible = compute_fov(grid, origin, radius)
    return [
        "".join(ch if Pos(x, y) in visible else " " for x, ch in enumerate(row))
        for y, row in enumerate(rows)
    ]


def test_open_room_is_fully_visible_walls_included() -> None:
    rows = ["#######", "#.....#", "#..@..#", "#.....#", "#######"]
    assert seen_art(rows, 20) == rows


def test_pillar_casts_a_widening_shadow() -> None:
    # The pillar hides slopes within 1/4 of the straight line east. (6,1) sits exactly on the
    # boundary and is seen; (7,1) is at slope 1/5 and is hidden. Far wall corners fall off too.
    rows = [
        "###########",
        "#.........#",
        "#.@.#.....#",
        "#.........#",
        "###########",
    ]
    assert seen_art(rows, 20) == [
        "#########  ",
        "#......    ",
        "#.@.#      ",
        "#......    ",
        "#########  ",
    ]


def test_closed_door_is_seen_but_blocks_what_is_behind_it() -> None:
    assert seen_art(["#######", "#.@+..#", "#######"], 20) == [
        "####   ",
        "#.@+   ",
        "####   ",
    ]


def test_open_door_does_not_block_sight() -> None:
    rows = ["#######", "#.@/..#", "#######"]
    assert seen_art(rows, 20) == rows


def test_radius_is_a_circle_not_a_square() -> None:
    rows = ["#.........#"] * 11
    rows[0] = rows[10] = "###########"
    rows[5] = "#....@....#"
    assert seen_art(rows, 3) == [
        "           ",
        "           ",
        "     .     ",
        "   .....   ",
        "   .....   ",
        "  ...@...  ",
        "   .....   ",
        "   .....   ",
        "     .     ",
        "           ",
        "           ",
    ]


def test_radius_zero_sees_only_the_origin() -> None:
    grid = grid_from_rows(["...", "...", "..."])
    assert compute_fov(grid, Pos(1, 1), 0) == frozenset({Pos(1, 1)})


def test_negative_radius_is_rejected() -> None:
    with pytest.raises(ValueError):
        compute_fov(grid_from_rows(["..."]), Pos(1, 0), -1)


def test_map_edge_counts_as_wall() -> None:
    grid = grid_from_rows(["...", "...", "..."])
    visible = compute_fov(grid, Pos(0, 0), 8)
    assert visible == {Pos(x, y) for x in range(3) for y in range(3)}


def test_a_wall_is_seen_and_hides_the_floor_behind_it() -> None:
    grid = grid_from_rows([".......", ".#.....", ".......", "......."])
    visible = compute_fov(grid, Pos(3, 2), 8)
    assert Pos(1, 1) in visible and Pos(0, 0) not in visible


def floors(grid: Grid) -> list[Pos]:
    return [
        Pos(x, y)
        for y in range(grid.height)
        for x in range(grid.width)
        if not blocks_sight(grid.get(x, y))
    ]


@pytest.mark.parametrize(("seed", "level"), [("BRASSLAMP42", 1), ("GOLD0007", 4), ("GOLD0033", 5)])
def test_sight_between_floor_tiles_is_symmetric(seed: str, level: int) -> None:
    spec = generate_level(Seed.parse(seed), level)
    grid = Grid(spec.width, spec.height, spec.tiles)
    cache: dict[Pos, frozenset[Pos]] = {}

    def fov(p: Pos) -> frozenset[Pos]:
        if p not in cache:
            cache[p] = compute_fov(grid, p, 8)
        return cache[p]

    open_tiles = floors(grid)
    checked = 0
    for a in open_tiles[::37]:
        for b in sorted(fov(a))[::5]:
            if not blocks_sight(grid.get(b.x, b.y)):
                assert a in fov(b), f"{a} sees {b} but not the reverse"
                checked += 1
    assert checked > 50


def test_a_wall_hides_the_room_behind_it() -> None:
    grid = grid_from_rows(["#########", "#...#...#", "#...#...#", "#...#...#", "#########"])
    visible = compute_fov(grid, Pos(2, 2), 20)
    assert Pos(4, 2) in visible
    assert not any(Pos(x, y) in visible for x in range(5, 9) for y in range(5))
