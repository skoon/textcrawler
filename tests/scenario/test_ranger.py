"""The Ranger: dual wielding (GDD 6.7) and Tracker (GDD 6.5)."""

from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import Attacked, Move, Wait
from minetoofar.sim.game import Game
from minetoofar.sim.statuses import apply_status
from tests.helpers import DATA, MINER, ScriptedRng, make_game

ROOM = ["#####", "#...#", "#.<.#", "#...#", "#####"]
VERMIN = "cave_vermin"
NORTH = (0, -1)  # monsters below the player face them: no flanking bonus muddies the numbers


def face(n: int) -> int:
    return n - 1


def stunned(game: Game) -> Game:
    for m in game.monsters:
        apply_status(m, "stunned", now=0, defs=DATA.statuses)
    return game


def swings(events: list[object]) -> list[Attacked]:
    return [e for e in events if isinstance(e, Attacked)]


# -- dual wielding -------------------------------------------------------------------------


def test_one_attack_action_swings_main_hand_then_off_hand() -> None:
    # main ATK +3 needs a 7; the off hand is at -4 (ATK -1) and needs an 11
    rng = ScriptedRng(
        [face(8), face(2), face(10)]
    )  # main hits for d6 2 + 1; off hand rolls 10: miss
    g = stunned(make_game(ROOM, [(MINER, (2, 3), "hunting", NORTH)], rng, class_id="ranger"))
    main, off = swings(g.submit(Move(0, 1)))
    assert (main.outcome, main.damage) == (Outcome.HIT, 2 + 1)
    assert off.outcome is Outcome.MISS and g.ticks == 100  # still one action


def test_the_off_hand_hits_at_eleven_and_adds_no_strength_to_damage() -> None:
    rng = ScriptedRng([face(8), face(2), face(11), face(4)])
    g = stunned(make_game(ROOM, [(MINER, (2, 3), "hunting", NORTH)], rng, class_id="ranger"))
    main, off = swings(g.submit(Move(0, 1)))
    assert off.outcome is Outcome.HIT and off.damage == 4  # d6 4, no +1 STR modifier
    assert rng.queue == []


def test_the_off_hand_swing_is_skipped_when_the_main_hand_kills() -> None:
    rng = ScriptedRng([face(8), face(5)])  # d6 5 + 1 = 6
    g = stunned(make_game(ROOM, [(MINER, (2, 3), "hunting", NORTH)], rng, class_id="ranger"))
    g.monsters[0].hp = 6
    assert len(swings(g.submit(Move(0, 1)))) == 1 and rng.queue == []


def test_a_fighter_with_a_shield_swings_once() -> None:
    rng = ScriptedRng([face(8), face(2)])
    g = stunned(make_game(ROOM, [(MINER, (2, 3), "hunting", NORTH)], rng))
    assert len(swings(g.submit(Move(0, 1)))) == 1 and rng.queue == []


# -- Tracker: sensing -------------------------------------------------------------------------

WALLED = ["############", "#<..#......#", "############"]


def sensed(g: Game) -> list[int]:
    return [m.id for m in g.view().sensed]


def test_enemies_inside_radius_five_are_sensed_through_walls() -> None:
    g = make_game(WALLED, [(MINER, (6, 1), "asleep"), (MINER, (7, 1), "asleep")], class_id="ranger")
    assert g.view().monsters == ()  # a wall is in the way: nothing is seen
    assert sensed(g) == [1]  # dx = 5 is exactly on the circle; dx = 6 is outside it


def test_the_tracker_circle_is_round_not_square() -> None:
    rows = ["#" * 12, "#<.........#"] + ["#" + "." * 10 + "#" for _ in range(8)] + ["#" * 12]
    g = make_game(rows, [(MINER, (4, 5), "asleep"), (MINER, (5, 5), "asleep")], class_id="ranger")
    # from (1,1): (4,5) is 3 across and 4 down, 9 + 16 = 25 (in); (5,5) is 16 + 16 = 32 (out)
    assert sensed(g) == [1] and g.view().monsters == ()


def test_a_monster_in_plain_view_is_seen_not_sensed() -> None:
    g = make_game(WALLED, [(MINER, (3, 1), "asleep")], class_id="ranger")
    assert [m.id for m in g.view().monsters] == [1] and sensed(g) == []


def test_only_rangers_sense() -> None:
    for class_id in ("fighter", "rogue"):
        g = make_game(WALLED, [(MINER, (6, 1), "asleep")], class_id=class_id)
        assert sensed(g) == [], class_id


def test_sensing_follows_the_ranger_and_gives_way_to_sight() -> None:
    rows = ["#" * 14, "#<" + "." * 11 + "#", "#" * 14]
    g = make_game(rows, [(MINER, (9, 1), "asleep")], ScriptedRng([5, 5]), class_id="ranger")
    assert sensed(g) == []  # dx 8
    for _ in range(4):
        g.submit(Move(1, 0))  # now at (5,1): dx 4, inside the lamp's reach
    assert sensed(g) == [] and [m.id for m in g.view().monsters] == [1]


# -- Tracker: beasts ------------------------------------------------------------------------


def test_rangers_hit_beasts_for_two_extra_on_every_blow() -> None:
    # Vermin DEF 2: main ATK +3 needs 9; off hand (ATK -1) needs 13
    rng = ScriptedRng([face(12), face(2), face(14), face(3)])
    g = stunned(make_game(ROOM, [(VERMIN, (2, 3), "hunting", NORTH)], rng, class_id="ranger"))
    g.monsters[0].hp = 30
    main, off = swings(g.submit(Move(0, 1)))
    assert main.damage == 2 + 1 + 2 and off.damage == 3 + 0 + 2


def test_undead_get_no_beast_bonus() -> None:
    rng = ScriptedRng([face(12), face(2), face(1)])
    g = stunned(make_game(ROOM, [(MINER, (2, 3), "hunting", NORTH)], rng, class_id="ranger"))
    assert swings(g.submit(Move(0, 1)))[0].damage == 2 + 1


def test_the_beast_bonus_is_the_rangers_alone() -> None:
    rng = ScriptedRng([face(15), face(2)])
    g = stunned(make_game(ROOM, [(VERMIN, (2, 3), "hunting", NORTH)], rng, class_id="fighter"))
    g.monsters[0].hp = 30
    assert swings(g.submit(Move(0, 1)))[0].damage == 2 + 3  # d8 2 + STR 3, nothing extra


def test_waiting_costs_the_ranger_nothing_extra() -> None:
    g = make_game(ROOM, class_id="ranger")
    g.submit(Wait())
    assert g.ticks == 100
