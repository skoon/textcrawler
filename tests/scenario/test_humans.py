"""Foreman Grimsby and Prospector Vane (GDD 7.6, 9.6): their tricks and their talk."""

from minetoofar.core.geometry import Pos
from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import Attacked, Killed, Move, Noticed, Spoke, Wait
from minetoofar.sim.statuses import is_active
from minetoofar.sim.traps import Trap
from tests.helpers import MINER, ScriptedRng, make_game

GRIMSBY, VANE, VERMIN = "foreman_grimsby", "prospector_vane", "cave_vermin"
LONG = ["#" * 20, "#<" + "." * 17 + "#", "#" * 20]
WIDE = [
    "#" * 20,
    "#<" + "." * 17 + "#",
    "#" + "." * 18 + "#",
    "#" * 20,
]  # room to walk round a trap
SPEECH = {
    "on_sight": "SIGHT",
    "on_hit": "HIT",
    "on_hurt": "HURT",
    "on_flee": "FLEE",
    "on_death": "DEATH",
}


def face(n: int) -> int:
    return n - 1


def said(events: list[object]) -> list[str]:
    return [e.text for e in events if isinstance(e, Spoke)]


def asleep(g, *ids: int) -> None:  # type: ignore[no-untyped-def]
    """Park monsters where they stand: they never take a turn."""
    for m in g.monsters:
        if m.id in ids:
            m.ready_at = 10**9


# -- Grimsby's aura ------------------------------------------------------------------------------


def test_grimsby_hurries_every_undead_within_five_tiles() -> None:
    g = make_game(
        LONG,
        [
            (GRIMSBY, (8, 1), "hunting"),
            (MINER, (10, 1), "asleep"),  # 2 away
            (VERMIN, (9, 1), "asleep"),  # a beast: not undead
            (MINER, (14, 1), "asleep"),  # 6 away: out of the circle
        ],
        ScriptedRng([]),
    )
    asleep(g, 2, 3, 4)
    g.submit(Wait())
    grimsby, near, beast, far = g.monsters
    assert is_active(near, "overtime", 0) and near.statuses["overtime"].ends == 300
    assert not is_active(beast, "overtime", 0) and not is_active(far, "overtime", 0)
    assert not is_active(grimsby, "overtime", 0)


def test_the_aura_is_renewed_every_turn() -> None:
    g = make_game(LONG, [(GRIMSBY, (8, 1), "hunting"), (MINER, (10, 1), "asleep")])
    asleep(g, 2)
    for _ in range(5):
        g.submit(Wait())
    assert g.monsters[1].statuses["overtime"].ends >= 500 + 100  # refreshed on his 500-tick turn


def test_with_undead_beside_him_grimsby_hangs_back_three_tiles_away() -> None:
    g = make_game(LONG, [(GRIMSBY, (8, 1), "hunting"), (MINER, (9, 1), "asleep")])
    asleep(g, 2)
    for _ in range(4):
        g.submit(Wait())
    assert g.monsters[0].pos == Pos(4, 1)  # three from the player at (1,1)
    for _ in range(3):
        g.submit(Wait())
    assert g.monsters[0].pos == Pos(4, 1)  # and he stays there


def test_grimsby_steps_back_if_you_get_closer_than_two() -> None:
    g = make_game(LONG, [(GRIMSBY, (2, 1), "hunting"), (MINER, (4, 1), "asleep")])
    asleep(g, 2)
    g.submit(Wait())
    assert g.monsters[0].pos == Pos(3, 1)


def test_grimsby_charges_when_no_undead_are_left_in_his_aura() -> None:
    g = make_game(LONG, [(GRIMSBY, (6, 1), "hunting")], ScriptedRng([face(1)] * 6))
    for _ in range(4):
        g.submit(Wait())
    assert g.monsters[0].pos == Pos(2, 1)
    assert any(isinstance(e, Attacked) and e.attacker == 1 for e in g.submit(Wait()))


def test_undead_outside_the_aura_do_not_hold_him_back() -> None:
    g = make_game(LONG, [(GRIMSBY, (6, 1), "hunting"), (MINER, (12, 1), "asleep")])
    asleep(g, 2)
    for _ in range(4):
        g.submit(Wait())
    assert g.monsters[0].pos == Pos(2, 1)


# -- the humans talk -----------------------------------------------------------------------------


def talker(rng: ScriptedRng, state: str = "idle", kind: str = GRIMSBY):  # type: ignore[no-untyped-def]
    g = make_game(LONG, [(kind, (4, 1), state)], rng)
    g.monsters[0].speech = dict(SPEECH)
    return g


def test_a_human_says_his_piece_when_he_first_notices_you_and_only_then() -> None:
    g = talker(ScriptedRng([face(1)] * 8))
    first = g.submit(Wait())
    assert Noticed(1, "Foreman Grimsby") in first and said(first) == ["SIGHT"]
    assert "SIGHT" not in said(g.submit(Wait()))


def test_a_human_taunts_after_landing_a_blow_but_not_every_turn() -> None:
    # Grimsby lands a blow on each of his turns (0, 100, 200 ...); he speaks at most every 500 ticks
    rng = ScriptedRng([face(15), face(1)] * 12)
    g = make_game(LONG, [(GRIMSBY, (2, 1), "hunting")], rng)
    g.monsters[0].speech = dict(SPEECH)
    lines = [said(g.submit(Wait())) for _ in range(7)]  # the swings at 0, 100, ... 600
    assert [i for i, line in enumerate(lines) if "HIT" in line] == [0, 5]


def test_a_human_cries_out_once_when_you_take_him_below_half_health() -> None:
    rng = ScriptedRng([face(15), face(8)] * 2 + [face(15), face(8)] + [face(1)] * 8)
    g = make_game(LONG, [(GRIMSBY, (2, 1), "hunting")], rng)
    g.monsters[0].speech = {"on_hurt": "HURT"}
    g.monsters[0].hp = 21  # 8 + 3 = 11 damage takes him to 10, under half of 40
    first = g.submit(Move(1, 0))
    assert "HURT" in said(first)
    assert "HURT" not in said(g.submit(Move(1, 0)))


def test_a_human_has_last_words() -> None:
    g = make_game(LONG, [(GRIMSBY, (2, 1), "hunting")], ScriptedRng([face(15), face(8)]))
    g.monsters[0].speech = dict(SPEECH)
    g.monsters[0].hp = 3
    events = g.submit(Move(1, 0))
    assert Killed(1, "Foreman Grimsby") in events and said(events) == ["DEATH"]
    assert events.index(Killed(1, "Foreman Grimsby")) < [type(e) for e in events].index(Spoke)


def test_monsters_without_speech_stay_silent() -> None:
    g = make_game(LONG, [(MINER, (4, 1), "idle")], ScriptedRng([face(1)] * 3))
    assert said(g.submit(Wait())) == []


# -- Prospector Vane ---------------------------------------------------------------------------


def vane(rng: ScriptedRng, pos: tuple[int, int] = (6, 1), rows: list[str] | None = None):  # type: ignore[no-untyped-def]
    g = make_game(rows or WIDE, [(VANE, pos, "hunting")], rng)
    g.monsters[0].speech = dict(SPEECH)
    return g


def test_vane_lays_a_hidden_trap_where_he_stands_then_runs() -> None:
    g = vane(ScriptedRng([0]))  # the trap kind: the first on the list
    events = g.submit(Wait())
    v = g.monsters[0]
    assert g.traps == [Trap(Pos(6, 1), "spring_trap")] and not g.traps[0].revealed
    assert v.traps_left == 3 and v.state == "fleeing" and said(events) == ["FLEE"]
    assert v.pos == Pos(6, 1)  # laying it took his turn
    g.submit(Wait())
    assert v.pos.x == 7  # now he runs, further from us


def test_vane_will_not_lay_a_trap_that_would_be_the_only_way_on() -> None:
    g = vane(ScriptedRng([face(1)] * 6), rows=LONG)  # a one-tile corridor: every tile is the way on
    events = g.submit(Wait())
    assert g.traps == [] and g.monsters[0].traps_left == 4
    assert any(isinstance(e, Attacked) for e in events) or g.monsters[0].state == "hunting"


def test_vane_will_not_shut_the_last_way_round_either() -> None:
    g = vane(ScriptedRng([0]))
    g.traps.append(Trap(Pos(6, 2), "spring_trap"))  # the lower lane is already trapped
    g.submit(Wait())
    assert len(g.traps) == 1  # laying one on the upper lane would shut the hall


def test_a_disarmed_trap_no_longer_counts_as_a_wall() -> None:
    g = vane(ScriptedRng([0]))
    trap = Trap(Pos(6, 2), "spring_trap")
    trap.disarmed = True
    g.traps.append(trap)
    g.submit(Wait())
    assert len(g.traps) == 2


def test_vane_picks_the_trap_kind_with_the_dice() -> None:
    g = vane(ScriptedRng([1]))
    g.submit(Wait())
    assert g.traps[0].kind == "tripwire_charge"


def test_vane_comes_back_to_the_fight_after_three_turns_of_retreat() -> None:
    g = vane(ScriptedRng([0]))
    for _ in range(4):
        g.submit(Wait())  # lays at 0, flees at 100, 200, and is hunting again at 300
    assert g.monsters[0].state == "hunting"


def test_vane_waits_six_turns_between_traps() -> None:
    g = vane(ScriptedRng([0, 0]))
    for _ in range(6):
        g.submit(Wait())
    assert len(g.traps) == 1  # at 600 he may lay another
    for _ in range(2):
        g.submit(Wait())
    assert len(g.traps) == 2


def test_vane_never_carries_more_than_four_traps() -> None:
    g = vane(ScriptedRng([0] * 8))
    g.monsters[0].traps_left = 1
    for _ in range(20):
        g.submit(Wait())
        if g.monsters[0].traps_left == 0:
            break
    assert g.monsters[0].traps_left == 0 and len(g.traps) == 1
    for _ in range(10):
        g.submit(Wait())
    assert len(g.traps) == 1


def test_vane_out_of_traps_just_fights() -> None:
    g = make_game(LONG, [(VANE, (2, 1), "hunting")], ScriptedRng([face(1)] * 3))
    g.monsters[0].traps_left = 0
    assert any(isinstance(e, Attacked) and e.attacker == 1 for e in g.submit(Wait()))
    assert g.traps == []


def test_vane_needs_to_see_you_within_six_tiles() -> None:
    far = vane(ScriptedRng([]), pos=(9, 1))  # seven away
    far.submit(Wait())
    assert far.traps == []
    behind = vane(ScriptedRng([]), pos=(5, 1), rows=["#" * 8, "#<.#...#", "#" * 8])
    behind.submit(Wait())
    assert behind.traps == []  # a wall between: no line of sight


def test_a_cornered_vane_fights() -> None:
    rows = ["#####", "#<..#", "#####"]
    g = make_game(rows, [(VANE, (3, 1), "fleeing")], ScriptedRng([face(1)] * 6))
    g.monsters[0].since = 0
    events = g.submit(Move(1, 0))
    assert any(isinstance(e, Attacked) and e.attacker == 1 for e in events)


def test_you_can_trip_a_trap_vane_laid() -> None:
    g = vane(ScriptedRng([0, face(3)]))
    g.submit(Wait())  # he lays it at (6,1) ...
    g.monsters[0].pos, g.monsters[0].ready_at = Pos(12, 1), 10**9  # ... and is out of the picture
    g.player.pos = Pos(5, 1)
    events = g.submit(Move(1, 0))
    assert any(type(e).__name__ == "TrapTriggered" for e in events) and g.traps == []


def test_a_fleeing_vane_is_fair_game_for_a_backstab() -> None:
    g = make_game(
        LONG,
        [(VANE, (2, 1), "fleeing", (1, 0))],
        ScriptedRng([face(15)] + [face(1)] * 3),
        class_id="rogue",
    )
    g.monsters[0].ready_at = 10**9
    hit = [e for e in g.submit(Move(1, 0)) if isinstance(e, Attacked)][0]
    assert hit.backstab and hit.outcome is Outcome.HIT
