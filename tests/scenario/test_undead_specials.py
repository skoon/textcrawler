"""Gravedigger Skeletons, Timecard Wraiths, and Miners that rise from graves (GDD 7.6)."""

from minetoofar.core.geometry import Pos
from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import (
    Attacked,
    Blocked,
    BlockReason,
    Move,
    Noticed,
    Rose,
    StatusApplied,
    Wait,
)
from tests.helpers import MINER, ScriptedRng, inert, make_game

SKELETON, WRAITH = "gravedigger_skeleton", "timecard_wraith"
HALL = ["#" * 14, "#<" + "." * 11 + "#", "#" * 14]


def face(n: int) -> int:
    return n - 1


def attacks(events: list[object]) -> list[Attacked]:
    return [e for e in events if isinstance(e, Attacked)]


# -- Gravedigger Skeleton ---------------------------------------------------------------------


def test_a_skeletons_natural_twenty_stuns_the_player() -> None:
    rng = ScriptedRng([face(20), face(1), face(1), face(1)])  # crit: 2d8, then its next swing
    g = make_game(HALL, [(SKELETON, (2, 1), "hunting")], rng, level=2)
    events = g.submit(Wait())
    assert StatusApplied(0, "Hale", "stunned") in events
    assert g.ticks == 200  # the stun costs a turn


def test_a_stun_leaves_three_turns_of_immunity() -> None:
    # two natural twenties in a row: the second finds the player immune
    rng = ScriptedRng([face(20), face(1), face(1), face(20), face(1), face(1)])
    g = make_game(HALL, [(SKELETON, (2, 1), "hunting")], rng, level=2)
    events = g.submit(Wait())
    assert sum(isinstance(e, StatusApplied) for e in events) == 1 and rng.queue == []
    assert g.ticks == 200


def test_an_ordinary_hit_does_not_stun() -> None:
    g = make_game(HALL, [(SKELETON, (2, 1), "hunting")], ScriptedRng([face(15), face(1)]), level=2)
    assert not any(isinstance(e, StatusApplied) for e in g.submit(Wait()))
    assert g.ticks == 100


def long_hall() -> list[str]:
    return ["#" * 20, "#<" + "." * 17 + "#", "#" * 20]


def test_a_skeletons_step_clangs_eight_steps_wide() -> None:
    # the skeleton steps from (10,1) to (9,1); the sleeper at (17,1) is 8 steps from there
    rng = ScriptedRng([0])
    g = make_game(
        long_hall(), [(SKELETON, (10, 1), "hunting"), (MINER, (17, 1), "asleep")], rng, level=2
    )
    events = g.submit(Wait())
    assert Noticed(2, "Shambling Miner") in events and g.monsters[1].state == "alerted"
    assert g.monsters[1].alert_pos == Pos(9, 1)  # it comes to where the noise was


def test_a_clang_nine_steps_off_is_not_heard() -> None:
    rng = ScriptedRng([])  # a wake roll would raise
    g = make_game(
        long_hall(), [(SKELETON, (10, 1), "hunting"), (MINER, (18, 1), "asleep")], rng, level=2
    )
    g.submit(Wait())
    assert g.monsters[1].state == "asleep"


def test_a_skeletons_swing_clangs_too() -> None:
    rng = ScriptedRng([face(1), 0])  # it misses; the sleeper next door wakes
    g = make_game(HALL, [(SKELETON, (2, 1), "hunting"), (MINER, (9, 1), "asleep")], rng, level=2)
    events = g.submit(Wait())
    assert Noticed(2, "Shambling Miner") in events


def test_a_clang_does_not_wake_the_skeleton_itself_or_other_hunters() -> None:
    rng = ScriptedRng([])
    g = make_game(HALL, [(SKELETON, (6, 1), "hunting"), (MINER, (7, 1), "hunting")], rng, level=2)
    g.submit(Wait())
    assert g.monsters[1].state == "hunting"


# -- Timecard Wraith ----------------------------------------------------------------------------


def test_a_wraith_walks_through_walls_straight_at_you() -> None:
    rows = ["#######", "#<.##.#", "#######"]
    g = make_game(rows, [(WRAITH, (5, 1), "hunting")], level=3)
    g.submit(Wait())
    g.submit(Wait())
    assert g.monsters[0].pos == Pos(3, 1)  # standing inside the wall, one step a turn


def test_a_wraith_cannot_end_its_move_on_another_actor() -> None:
    rows = ["#######", "#<.##.#", "#######"]
    g = make_game(rows, [(WRAITH, (5, 1), "hunting"), (WRAITH, (4, 1), "asleep")], level=3)
    g.monsters[1].ready_at = 10**9
    g.submit(Wait())
    assert g.monsters[0].pos == Pos(4, 2)  # round the sleeper, through the wall below


def test_a_wraith_inside_a_wall_has_four_extra_defense_and_can_still_be_hit() -> None:
    rows = ["#####", "#<#.#", "#####"]
    # Fighter ATK +5 vs DEF 4 needs 9; inside the wall (DEF 8) it needs 13
    wall = inert(make_game(rows, [(WRAITH, (2, 1), "hunting")], ScriptedRng([face(12)]), level=3))
    assert attacks(wall.submit(Move(1, 0)))[0].outcome is Outcome.MISS
    wall = inert(
        make_game(rows, [(WRAITH, (2, 1), "hunting")], ScriptedRng([face(13), face(1)]), level=3)
    )
    assert attacks(wall.submit(Move(1, 0)))[0].outcome is Outcome.HIT
    floor = ["#####", "#<.##", "#####"]
    open_ground = inert(
        make_game(floor, [(WRAITH, (2, 1), "hunting")], ScriptedRng([face(9), face(1)]), level=3)
    )
    assert attacks(open_ground.submit(Move(1, 0)))[0].outcome is Outcome.HIT


def test_a_wraith_senses_you_through_walls_but_a_miner_does_not() -> None:
    rows = ["#########", "#<.#....#", "#########"]
    g = make_game(rows, [(WRAITH, (5, 1), "idle"), (MINER, (6, 1), "idle")], level=3)
    events = g.submit(Wait())
    assert g.monsters[0].state == "hunting" and Noticed(1, "Timecard Wraith") in events
    assert g.monsters[1].state == "idle"


def test_a_wraith_hit_can_clock_you_in() -> None:
    # Wraith ATK +5 at level 3 needs a 6 against DEF 1; d4; then the 35% roll: 0 succeeds
    rng = ScriptedRng([face(8), face(3), 0, face(1)])
    g = make_game(HALL, [(WRAITH, (2, 1), "hunting")], rng, level=3)
    events = g.submit(Wait())
    assert StatusApplied(0, "Hale", "clocked_in") in events
    assert g.ticks == 200  # the lost action


def test_clocked_in_players_get_no_second_roll_for_five_turns() -> None:
    rng = ScriptedRng([face(8), face(3), 0, face(8), face(3)])  # a third draw would raise
    g = make_game(HALL, [(WRAITH, (2, 1), "hunting")], rng, level=3)
    events = g.submit(Wait())  # clocked in at 0; the Wraith swings again at 100 (no roll)
    assert sum(isinstance(e, StatusApplied) for e in events) == 1
    assert len(attacks(events)) == 2 and rng.queue == []


def test_a_hit_that_fails_the_roll_does_nothing_extra() -> None:
    rng = ScriptedRng([face(8), face(3), 50])
    g = make_game(HALL, [(WRAITH, (2, 1), "hunting")], rng, level=3)
    assert not any(isinstance(e, StatusApplied) for e in g.submit(Wait()))
    assert g.ticks == 100 and rng.queue == []


# -- Miners in open graves ---------------------------------------------------------------------


def test_a_buried_miner_is_hidden_and_not_even_sensed() -> None:
    g = make_game(HALL, [(MINER, (3, 1), "buried")], class_id="ranger")
    assert g.view().monsters == () and g.view().sensed == ()


def test_a_buried_miner_rises_when_you_come_within_three_tiles() -> None:
    far = make_game(HALL, [(MINER, (5, 1), "buried")])  # four away
    far.submit(Wait())
    assert far.monsters[0].state == "buried"
    near = make_game(HALL, [(MINER, (4, 1), "buried")])  # three away
    events = near.submit(Wait())
    assert Rose(1, "Shambling Miner") in events and near.monsters[0].state == "hunting"
    assert [m.id for m in near.view().monsters] == [1]


def test_rising_takes_the_miners_whole_turn() -> None:
    g = make_game(HALL, [(MINER, (4, 1), "buried")])
    g.submit(Wait())
    assert g.monsters[0].pos == Pos(4, 1) and g.monsters[0].ready_at == 100


def test_you_cannot_walk_into_a_grave_that_is_occupied() -> None:
    g = inert(make_game(HALL, [(MINER, (2, 1), "buried")]))
    assert g.submit(Move(1, 0)) == [Blocked(Pos(2, 1), BlockReason.OCCUPIED)]
    assert g.ticks == 0
