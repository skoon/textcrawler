import pytest

from minetoofar.core.geometry import DIRS8, Pos, direction_to, in_rear_arc, octile
from minetoofar.core.grid import Grid, Tile, blocks_sight, is_walkable
from minetoofar.core.pathing import distance_map
from minetoofar.core.rng import Rng
from tests.helpers import grid_from_rows

N, NE, E, SE, S, SW, W, NW = DIRS8


def test_direction_order_is_clockwise_from_north() -> None:
    assert DIRS8 == ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))


def test_octile_distance_uses_14_and_10() -> None:
    assert octile(Pos(0, 0), Pos(3, 1)) == 34
    assert octile(Pos(2, 2), Pos(2, 2)) == 0
    assert octile(Pos(0, 0), Pos(0, 5)) == 50


@pytest.mark.parametrize(
    ("tile", "walkable"),
    [
        (Tile.SOLID, False), (Tile.WALL, False), (Tile.ROCK, False),
        (Tile.FLOOR, True), (Tile.CAVE_FLOOR, True), (Tile.DOOR, True),
        (Tile.ENTRY, True), (Tile.EXIT, True), (Tile.DOOR_OPEN, True),
        (Tile.BRINE, True), (Tile.RUBBLE, True), (Tile.OPEN_GRAVE, True),
        (Tile.GRAVESTONE, False), (Tile.MONUMENT, False),
    ],
)  # fmt: skip
def test_walkable_tiles(tile: Tile, walkable: bool) -> None:
    assert is_walkable(tile) is walkable


def test_grid_get_set_and_bounds() -> None:
    g = Grid(4, 3)
    assert g.get(1, 1) == Tile.SOLID
    g.set(1, 1, Tile.FLOOR)
    assert g.get(1, 1) == Tile.FLOOR
    assert g.in_bounds(3, 2) and not g.in_bounds(4, 2) and not g.in_bounds(-1, 0)
    with pytest.raises(IndexError):
        g.get(4, 0)


def test_orthogonal_step_needs_walkable_destination() -> None:
    g = grid_from_rows(["#.#"])
    assert g.can_step(Pos(1, 0), E) is False
    assert g.can_step(Pos(1, 0), N) is False  # out of bounds
    g2 = grid_from_rows(["..#"])
    assert g2.can_step(Pos(0, 0), E) is True
    assert g2.can_step(Pos(1, 0), E) is False


def test_diagonal_step_cannot_cut_a_corner() -> None:
    open_room = grid_from_rows(["...", "...", "..."])
    assert open_room.can_step(Pos(0, 0), SE) is True
    wall_beside = grid_from_rows([".#.", "...", "..."])
    assert wall_beside.can_step(Pos(0, 0), SE) is False  # (1,0) is a wall


def test_diagonal_steps_through_doors_are_refused() -> None:
    g = grid_from_rows(["...", ".+.", "..."])
    assert g.can_step(Pos(0, 0), SE) is False  # into a door
    assert g.can_step(Pos(1, 1), SE) is False  # out of a door
    assert g.can_step(Pos(0, 1), E) is True  # orthogonal is fine


def test_open_doors_keep_the_no_diagonal_rule() -> None:
    g = grid_from_rows(["...", "./.", "..."])
    assert g.can_step(Pos(0, 0), SE) is False
    assert g.can_step(Pos(1, 1), SE) is False
    assert g.can_step(Pos(0, 1), E) is True


@pytest.mark.parametrize(
    ("tile", "blocks"),
    [
        (Tile.SOLID, True), (Tile.WALL, True), (Tile.ROCK, True), (Tile.DOOR, True),
        (Tile.FLOOR, False), (Tile.CAVE_FLOOR, False), (Tile.DOOR_OPEN, False),
        (Tile.ENTRY, False), (Tile.EXIT, False),
        (Tile.BRINE, False), (Tile.RUBBLE, False), (Tile.OPEN_GRAVE, False),
        (Tile.GRAVESTONE, False), (Tile.MONUMENT, True),
    ],
)  # fmt: skip
def test_sight_blocking_tiles(tile: Tile, blocks: bool) -> None:
    assert blocks_sight(tile) is blocks


def test_distance_map_orthogonal_and_diagonal_costs() -> None:
    g = grid_from_rows(["....", "...."])
    d = distance_map(g, Pos(0, 0))
    assert d[Pos(3, 0)] == 30
    assert d[Pos(1, 1)] == 14
    assert d[Pos(3, 1)] == 34  # one diagonal plus two straight steps
    assert len(d) == 8


def test_distance_map_routes_around_walls_without_cutting_corners() -> None:
    g = grid_from_rows(["..#..", "..#..", "....."])
    d = distance_map(g, Pos(0, 0))
    assert d[Pos(4, 0)] == 68  # 14 + 10 + 10 + 10 + 14 + 10


def test_distance_map_omits_unreachable_tiles() -> None:
    sealed = grid_from_rows(["..#..", "..#.."])
    assert Pos(4, 0) not in distance_map(sealed, Pos(0, 0))


def reference_can_step(grid: Grid, pos: Pos, d: tuple[int, int]) -> bool:
    """The movement rule written the slow, obvious way (GDD 7.1)."""
    nx, ny = pos.x + d[0], pos.y + d[1]
    if not grid.in_bounds(nx, ny) or not is_walkable(grid.get(nx, ny)):
        return False
    if d[0] == 0 or d[1] == 0:
        return True
    doors = (Tile.DOOR, Tile.DOOR_OPEN)
    if grid.get(pos.x, pos.y) in doors or grid.get(nx, ny) in doors:
        return False
    solid = (Tile.SOLID, Tile.WALL, Tile.ROCK)
    return all(
        grid.in_bounds(ox, oy) and grid.get(ox, oy) not in solid
        for ox, oy in ((nx, pos.y), (pos.x, ny))
    )


def test_can_step_agrees_with_the_plain_statement_of_the_rule_on_random_grids() -> None:
    rng = Rng(2024)
    tiles = list(Tile)
    for _ in range(40):
        grid = Grid(9, 7)
        for y in range(7):
            for x in range(9):
                grid.set(x, y, tiles[rng.below(len(tiles))])
        for y in range(7):
            for x in range(9):
                for d in DIRS8:
                    assert grid.can_step(Pos(x, y), d) == reference_can_step(grid, Pos(x, y), d)


def test_distance_map_can_stop_once_the_wanted_tiles_are_settled() -> None:
    g = grid_from_rows(["..........", ".........."])
    full = distance_map(g, Pos(0, 0))
    early = distance_map(g, Pos(0, 0), until=[Pos(2, 1)])
    assert early[Pos(2, 1)] == full[Pos(2, 1)] == 24
    assert Pos(9, 1) not in early and len(early) < len(full)
    assert all(full[p] == cost for p, cost in early.items())  # nothing tentative leaks out


def test_distance_map_with_a_wanted_tile_that_cannot_be_reached_is_the_full_map() -> None:
    g = grid_from_rows(["..#.."])
    assert distance_map(g, Pos(0, 0), until=[Pos(4, 0)]) == distance_map(g, Pos(0, 0))


def test_direction_to_gives_the_sign_of_each_axis() -> None:
    assert direction_to(Pos(5, 5), Pos(9, 5)) == (1, 0)
    assert direction_to(Pos(5, 5), Pos(4, 1)) == (-1, -1)
    assert direction_to(Pos(5, 5), Pos(5, 5)) == (0, 0)


def test_rear_arc_is_the_three_tiles_opposite_the_facing() -> None:
    target = Pos(5, 5)
    flanking = {
        d: sorted(o for o in DIRS8 if in_rear_arc(target.step(o), target, d)) for d in DIRS8
    }
    assert flanking[N] == sorted([S, SW, SE])  # facing north: south, south-west, south-east
    assert flanking[NE] == sorted([SW, S, W])
    assert flanking[E] == sorted([W, NW, SW])
    assert flanking[SW] == sorted([NE, N, E])


@pytest.mark.parametrize("facing", DIRS8)
def test_every_facing_has_exactly_three_flanking_neighbours_and_never_the_front(
    facing: tuple[int, int],
) -> None:
    target = Pos(5, 5)
    flanking = [o for o in DIRS8 if in_rear_arc(target.step(o), target, facing)]
    assert len(flanking) == 3
    assert facing not in flanking
    assert (-facing[0], -facing[1]) in flanking  # straight behind is always in the arc


def test_standing_on_the_target_is_never_flanking() -> None:
    assert in_rear_arc(Pos(2, 2), Pos(2, 2), N) is False


def test_rubble_doubles_the_cost_of_the_step_onto_it() -> None:
    g = grid_from_rows(["..:.."])
    d = distance_map(g, Pos(0, 0))
    assert [d[Pos(x, 0)] for x in range(5)] == [0, 10, 30, 40, 50]  # 10 + 20, then 10 each


def test_rubble_makes_a_detour_worth_taking() -> None:
    g = grid_from_rows(["..:..", "....."])
    assert distance_map(g, Pos(0, 0))[Pos(4, 0)] == 48  # three straight steps and two diagonals


def test_props_that_block_movement_still_let_a_diagonal_pass_between_them() -> None:
    g = grid_from_rows([".T.", "...", ".H."])
    assert g.can_step(Pos(0, 0), SE) is True  # only walls and rock stop corner-cutting
    assert g.can_step(Pos(1, 1), N) is False and g.can_step(Pos(1, 1), S) is False


# -- how much of the level can be walked to --------------------------------------------------------


def test_count_reachable_counts_the_connected_walkable_tiles() -> None:
    g = grid_from_rows(["#######", "#<...##", "##.#.##", "#.....#", "#######"])
    assert g.count_reachable(Pos(1, 1)) == 11
    assert g.count_reachable(Pos(0, 0)) == 0  # a wall is not a place to start


def test_walling_off_a_corridor_tile_cuts_off_what_is_behind_it() -> None:
    g = grid_from_rows(["#########", "#<.....>#", "#########"])
    assert g.count_reachable(Pos(1, 1)) == 7
    assert g.count_reachable(Pos(1, 1), [Pos(4, 1)]) == 3


def test_a_loop_has_a_way_round() -> None:
    g = grid_from_rows(["#######", "#<....#", "#.###.#", "#.....#", "#######"])
    total = g.count_reachable(Pos(1, 1))
    assert g.count_reachable(Pos(1, 1), [Pos(3, 1)]) == total - 1  # only the tile itself is lost


def test_a_blocked_start_reaches_nothing() -> None:
    g = grid_from_rows(["#####", "#<..#", "#####"])
    assert g.count_reachable(Pos(1, 1), [Pos(1, 1)]) == 0
