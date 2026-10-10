"""Noise (GDD 7.7): what a sound wakes, who comes to look, and what stops it."""

from minetoofar.core.geometry import Pos
from minetoofar.sim.events import Move, Noticed, Wait
from tests.helpers import MINER, ScriptedRng, make_game

# The player at (1,1); the corridor turns south at x=5 and nothing there can see back along it.
CORNER = ["#######", "#<....#", "#####.#", "#####.#", "#####.#", "#######"]
WITH_DOOR = ["#######", "#<....#", "#####+#", "#####.#", "#######"]


def face(n: int) -> int:
    return n - 1


def swing_at_a_dummy(rows: list[str], listener: tuple[str, tuple[int, int], str], rng: ScriptedRng):  # type: ignore[no-untyped-def]
    """The player attacks an inert dummy beside them (and misses); `listener` hears the swing."""
    g = make_game(rows, [("shambling_miner", (2, 1), "hunting"), listener], rng)
    g.monsters[0].ready_at = 10**9
    g.submit(Move(1, 0))
    return g, g.monsters[1]


def test_a_melee_swing_alerts_an_idle_monster_within_five_steps() -> None:
    g, ear = swing_at_a_dummy(CORNER, (MINER, (5, 3), "idle"), ScriptedRng([face(1)]))
    assert ear.state == "alerted" and ear.alert_pos == Pos(1, 1)
    assert ear.pos == Pos(5, 2)  # and it has already started walking toward the sound


def test_a_sound_six_steps_away_is_not_heard() -> None:
    g, ear = swing_at_a_dummy(CORNER, (MINER, (5, 4), "idle"), ScriptedRng([face(1)]))
    assert ear.state == "idle" and ear.pos == Pos(5, 4)


def test_a_closed_door_muffles_the_noise_and_an_open_one_does_not() -> None:
    _, shut = swing_at_a_dummy(WITH_DOOR, (MINER, (5, 3), "idle"), ScriptedRng([face(1)]))
    assert shut.state == "idle"
    opened = [row.replace("+", "/") for row in WITH_DOOR]
    _, heard = swing_at_a_dummy(opened, (MINER, (5, 3), "idle"), ScriptedRng([face(1)]))
    assert heard.state == "alerted"


def test_a_sleeper_that_hears_it_wakes_one_time_in_two() -> None:
    rng = ScriptedRng([face(1), 0])  # the swing misses; the wake roll succeeds
    g, ear = swing_at_a_dummy(CORNER, (MINER, (5, 3), "asleep"), rng)
    assert ear.state == "alerted" and ear.alert_pos == Pos(1, 1) and rng.queue == []
    rng = ScriptedRng([face(1), 1])  # ... or does not
    g, ear = swing_at_a_dummy(CORNER, (MINER, (5, 3), "asleep"), rng)
    assert ear.state == "asleep" and rng.queue == []


def test_the_wake_up_is_announced() -> None:
    g = make_game(
        CORNER,
        [("shambling_miner", (2, 1), "hunting"), (MINER, (5, 3), "asleep")],
        ScriptedRng([face(1), 0]),
    )
    g.monsters[0].ready_at = 10**9
    assert Noticed(2, "Shambling Miner") in g.submit(Move(1, 0))


def test_hunters_and_the_hidden_ignore_noise() -> None:
    rng = ScriptedRng([face(1)])
    g = make_game(
        CORNER,
        [
            ("shambling_miner", (2, 1), "hunting"),
            (MINER, (4, 1), "hunting"),
            (MINER, (5, 3), "buried"),
            ("blind_ore_eel", (5, 2), "submerged"),
        ],
        rng,
    )
    for m in g.monsters:
        m.ready_at = 10**9
    g.submit(Move(1, 0))
    assert [m.state for m in g.monsters] == ["hunting", "hunting", "buried", "submerged"]
    assert rng.queue == []  # no wake rolls were spent on them


def test_opening_a_door_makes_a_noise_of_radius_three() -> None:
    rows = ["#############", "#<.+........#", "#############"]
    # The sleeper is 3 steps past the door. It also rolls its own "someone is near" wake-up each
    # turn (4 tiles from (2,1)), so the script holds those three rolls and the noise roll between.
    rng = ScriptedRng([5, 1, 5, 5])
    near = make_game(rows, [(MINER, (6, 1), "asleep")], rng)
    near.submit(Move(1, 0))  # to (2,1)
    near.submit(Move(1, 0))  # the bump that opens the door: the noise roll (1: sleeps on)
    near.submit(Move(1, 0))
    assert rng.queue == [] and near.monsters[0].state == "asleep"  # the roll was spent: it heard
    far = make_game(rows, [(MINER, (8, 1), "asleep")], ScriptedRng([]))  # 5 steps: out of range
    for _ in range(3):
        far.submit(Move(1, 0))
    assert far.monsters[0].state == "asleep"


def test_an_alerted_monster_that_catches_sight_of_the_player_starts_hunting() -> None:
    g = make_game(CORNER, [(MINER, (5, 3), "alerted")])
    g.monsters[0].alert_pos = Pos(5, 1)
    events = []
    for _ in range(6):
        events += g.submit(Wait())
    assert g.monsters[0].state == "hunting" and any(isinstance(e, Noticed) for e in events)


def test_an_alerted_monster_standing_where_the_noise_was_gives_up_and_goes_idle() -> None:
    g = make_game(CORNER, [(MINER, (5, 3), "alerted")])
    g.monsters[0].alert_pos = Pos(5, 3)
    g.submit(Wait())
    assert g.monsters[0].state == "idle" and g.monsters[0].alert_pos is None
