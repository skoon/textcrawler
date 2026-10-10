"""The pure helpers behind monster decisions: noise, the flee map, phasing, brine paths."""

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.core.pathing import distance_map
from minetoofar.sim import ai
from tests.helpers import grid_from_rows


def test_noise_spreads_the_given_number_of_steps_through_open_floor() -> None:
    g = grid_from_rows(["..........", ".........."])
    heard = ai.noise_reach(g, Pos(0, 0), 3)
    assert Pos(3, 0) in heard and Pos(3, 1) in heard and Pos(4, 0) not in heard
    assert Pos(0, 0) in heard


def test_noise_does_not_cross_walls_but_goes_around_them() -> None:
    g = grid_from_rows(["....#....", "....#....", "........."])
    assert Pos(5, 0) not in ai.noise_reach(g, Pos(3, 0), 3)  # the wall hides it for three steps
    assert Pos(5, 0) in ai.noise_reach(g, Pos(3, 0), 5)  # round the bottom, five steps


def test_a_closed_door_stops_noise_and_an_open_one_does_not() -> None:
    closed = grid_from_rows([".+."])
    assert Pos(2, 0) not in ai.noise_reach(closed, Pos(0, 0), 5)
    opened = grid_from_rows(["./."])
    assert Pos(2, 0) in ai.noise_reach(opened, Pos(0, 0), 5)


def test_the_flee_map_leads_away_from_the_player() -> None:
    g = grid_from_rows(["#########", "#.......#", "#########"])
    flee = ai.flee_map(g, distance_map(g, Pos(4, 1)))
    assert flee[Pos(1, 1)] < flee[Pos(2, 1)] < flee[Pos(3, 1)] < flee[Pos(4, 1)]  # lower is safer
    assert ai.flee_step(g, flee, Pos(2, 1), set()) == (-1, 0)
    assert ai.flee_step(g, flee, Pos(6, 1), set()) == (1, 0)


def test_a_cornered_monster_has_no_flee_step() -> None:
    g = grid_from_rows(["#####", "#...#", "#####"])
    flee = ai.flee_map(g, distance_map(g, Pos(3, 1)))
    assert ai.flee_step(g, flee, Pos(1, 1), set()) is None  # the dead end is as safe as it gets


def test_flee_steps_skip_occupied_tiles() -> None:
    g = grid_from_rows(["#######", "#.....#", "#.....#", "#######"])
    flee = ai.flee_map(g, distance_map(g, Pos(5, 1)))
    open_step = ai.flee_step(g, flee, Pos(3, 1), set())
    assert open_step is not None
    blocked = {Pos(3, 1).step(open_step)}
    other = ai.flee_step(g, flee, Pos(3, 1), blocked)
    assert other != open_step


def test_phasing_monsters_head_straight_for_the_target_through_walls() -> None:
    assert ai.phase_step(Pos(0, 0), Pos(5, 0), set()) == (1, 0)
    assert ai.phase_step(Pos(0, 0), Pos(5, 5), set()) == (1, 1)
    assert ai.phase_step(Pos(5, 5), Pos(0, 0), set()) == (-1, -1)


def test_phasing_monsters_walk_round_whoever_stands_in_the_way() -> None:
    step = ai.phase_step(Pos(0, 0), Pos(5, 0), {Pos(1, 0)})
    assert step in ((1, 1), (1, -1))


def test_phasers_stay_on_the_map() -> None:
    assert ai.phase_step(Pos(0, 0), Pos(0, -5), set(), bounds=(10, 10)) is None
    assert ai.phase_step(Pos(0, 0), Pos(-3, 3), set(), bounds=(10, 10)) == (0, 1)


def test_a_phaser_with_every_closer_tile_taken_waits() -> None:
    blocked = {Pos(1, 0), Pos(1, 1), Pos(1, -1)}
    assert ai.phase_step(Pos(0, 0), Pos(5, 0), blocked) is None


def test_phaser_reach_ignores_walls_and_corners() -> None:
    g = grid_from_rows(["#.#", ".#.", "#.#"])
    assert ai.attack_direction(g, Pos(1, 1), Pos(0, 0), phasing=True) == (-1, -1)
    assert ai.attack_direction(g, Pos(1, 1), Pos(0, 0)) is None
    assert ai.attack_direction(g, Pos(1, 1), Pos(2, 2), phasing=True) == (1, 1)
    assert ai.attack_direction(g, Pos(1, 1), Pos(1, 1), phasing=True) is None


def test_brine_only_distance_maps_never_leave_the_water() -> None:
    g = grid_from_rows(["#######", "#..~~~#", "#..~.~#", "#..~~~#", "#######"])
    d = distance_map(g, Pos(2, 2), only=frozenset({Tile.BRINE}))
    assert Pos(3, 1) in d and Pos(5, 3) in d
    assert Pos(1, 1) not in d and Pos(4, 2) not in d  # dry tiles are out
