"""Cave Vermin swarms, Blind Ore-Eels, and Gem Badgers (GDD 7.6)."""

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import (
    Attacked,
    Blocked,
    BlockReason,
    Burrowed,
    Fled,
    Move,
    Surfaced,
    UseAbility,
    Wait,
)
from tests.helpers import MINER, ScriptedRng, inert, make_game

VERMIN, EEL, BADGER = "cave_vermin", "blind_ore_eel", "gem_badger"
HALL = ["#" * 14, "#<" + "." * 11 + "#", "#" * 14]
ARENA = [
    "#######",
    "#.....#",
    "#.....#",
    "#..<..#",
    "#.....#",
    "#.....#",
    "#######",
]  # player (3,3)
POND = ["######", "#<~~.#", "######"]  # the player at (1,1); brine at (2,1) and (3,1)


def face(n: int) -> int:
    return n - 1


def swings(events: list[object]) -> list[Attacked]:
    return [e for e in events if isinstance(e, Attacked)]


# -- Cave Vermin: the swarm bonus --------------------------------------------------------------


# Spots beside the player at (3,3) but not behind them (the player faces south, so the rear arc
# is the row above, where a flanking bonus would muddy the numbers).
BESIDE = [(3, 4), (2, 4), (4, 4), (2, 3), (4, 3)]


def vermin_swing(others: int, roll: int) -> Outcome:
    """One Vermin swings at the Fighter while `others` more stand beside them but cannot act."""
    spots = BESIDE[: others + 1]
    g = make_game(ARENA, [(VERMIN, p, "hunting") for p in spots], ScriptedRng([face(roll), 0]))
    for m in g.monsters[1:]:
        m.ready_at = 10**9
    return swings(g.submit(Wait()))[0].outcome


def test_each_other_vermin_beside_the_target_adds_one_to_hit() -> None:
    # Vermin ATK +1 against DEF 1 needs an 11 in all: a roll of 8 gets there with two others
    assert vermin_swing(0, 8) is Outcome.MISS  # 8 + 1 = 9
    assert vermin_swing(1, 8) is Outcome.MISS  # 10
    assert vermin_swing(2, 8) is Outcome.HIT  # 11


def test_the_swarm_bonus_stops_at_three() -> None:
    assert vermin_swing(4, 6) is Outcome.MISS  # 6 + 1 + 3 = 10: a fourth other adds nothing
    assert vermin_swing(4, 7) is Outcome.HIT


def test_only_vermin_count_for_the_swarm() -> None:
    g = make_game(
        ARENA,
        [(VERMIN, (3, 4), "hunting"), (MINER, (2, 4), "hunting"), (MINER, (4, 4), "hunting")],
        ScriptedRng([face(8)]),
    )
    for m in g.monsters[1:]:
        m.ready_at = 10**9
    assert swings(g.submit(Wait()))[0].outcome is Outcome.MISS


def test_vermin_cover_two_tiles_for_every_one_the_player_walks() -> None:
    g = make_game(HALL, [(VERMIN, (9, 1), "hunting")])
    g.submit(Wait())
    assert g.monsters[0].pos == Pos(7, 1)


# -- Blind Ore-Eel ---------------------------------------------------------------------------


def test_a_submerged_eel_is_invisible_and_unlisted() -> None:
    g = make_game(POND, [(EEL, (3, 1), "submerged")])
    assert g.view().monsters == () and g.view().sensed == ()


def test_an_eel_ambushes_whoever_steps_beside_it_with_four_extra_attack() -> None:
    # Eel ATK +4 against DEF 1 needs a 7; the ambush's +4 means a 3 is enough. d6 1 + 2 - DR 2 -> 1.
    g = make_game(
        ["######", "#.<~.#", "######"],
        [(EEL, (3, 1), "submerged")],
        ScriptedRng([face(3), face(1)]),
    )
    events = g.submit(Wait())
    assert Surfaced(1, "Blind Ore-Eel") in events
    assert swings(events)[0].outcome is Outcome.HIT
    assert g.monsters[0].state == "hunting" and [m.id for m in g.view().monsters] == [1]


def test_a_surfaced_eel_gets_no_such_bonus_on_a_plain_swing() -> None:
    g = make_game(
        ["######", "#.<~.#", "######"], [(EEL, (3, 1), "hunting")], ScriptedRng([face(3)])
    )
    g.monsters[0].since = 0
    assert swings(g.submit(Wait()))[0].outcome is Outcome.MISS  # 3 + 4 = 7 < 11


def test_the_ranger_cannot_be_ambushed() -> None:
    # Ranger DEF 2: the Eel needs 8 plain, or 4 with the ambush; a 5 hits only if ambushed.
    g = make_game(
        ["######", "#.<~.#", "######"],
        [(EEL, (3, 1), "submerged")],
        ScriptedRng([face(5)]),
        class_id="ranger",
    )
    assert swings(g.submit(Wait()))[0].outcome is Outcome.MISS


def test_a_submerged_eel_waits_while_nobody_is_beside_it() -> None:
    g = make_game(POND, [(EEL, (3, 1), "submerged")], ScriptedRng([]))
    g.submit(Wait())
    assert g.monsters[0].state == "submerged" and g.monsters[0].pos == Pos(3, 1)


def test_you_cannot_attack_or_walk_into_a_submerged_eel() -> None:
    g = make_game(["######", "#<~..#", "######"], [(EEL, (2, 1), "submerged")])
    g.monsters[0].ready_at = 10**9
    assert g.submit(Move(1, 0)) == [Blocked(Pos(2, 1), BlockReason.OCCUPIED)]


def test_cleave_ignores_submerged_eels() -> None:
    g = make_game(["######", "#<~..#", "######"], [(EEL, (2, 1), "submerged")], rank=3)
    g.monsters[0].ready_at = 10**9
    assert g.adjacent_enemies() == []


def test_a_surfaced_eel_follows_through_the_brine_but_never_onto_dry_ground() -> None:
    rows = ["##########", "#<..~~~..#", "##########"]
    g = make_game(rows, [(EEL, (6, 1), "hunting")], ScriptedRng([face(1)] * 8))
    g.monsters[0].since = 0
    for _ in range(3):
        g.submit(Move(1, 0))  # wade toward the Eel
    assert all(g.grid.get(m.pos.x, m.pos.y) == Tile.BRINE for m in g.monsters)


def test_an_eel_dives_again_after_two_turns_with_nobody_beside_it() -> None:
    g = make_game(["###########", "#<...~~~..#", "###########"], [(EEL, (6, 1), "hunting")])
    g.monsters[0].since = 0
    for _ in range(3):
        g.submit(Wait())  # the player is out of its reach (sight 2); its turns at 0, 100, 200
    assert g.monsters[0].state == "submerged"


def test_an_eel_keeps_fighting_while_someone_is_beside_it() -> None:
    g = make_game(
        ["######", "#.<~.#", "######"], [(EEL, (3, 1), "hunting")], ScriptedRng([face(1)] * 6)
    )
    g.monsters[0].since = 0
    for _ in range(4):
        g.submit(Wait())
    assert g.monsters[0].state == "hunting"


# -- Gem Badger ---------------------------------------------------------------------------------


def test_a_healthy_badger_hunts_like_any_beast() -> None:
    g = make_game(HALL, [(BADGER, (9, 1), "hunting")])
    g.submit(Wait())  # two steps of 80 fit before the player's 100
    assert g.monsters[0].pos == Pos(7, 1) and g.monsters[0].ready_at == 160


def test_a_badger_flees_at_forty_percent_health() -> None:
    g = make_game(HALL, [(BADGER, (2, 1), "hunting")])
    g.monsters[0].hp = 6  # 16 * 40% = 6.4
    events = g.submit(Wait())
    assert Fled(1, "Gem Badger") in events and g.monsters[0].state == "fleeing"
    assert g.monsters[0].pos == Pos(4, 1) and g.monsters[0].ready_at == 160  # two steps of 80


def test_a_badger_just_above_the_line_keeps_fighting() -> None:
    g = make_game(HALL, [(BADGER, (2, 1), "hunting")], ScriptedRng([face(1)]))
    g.monsters[0].hp = 7
    g.submit(Wait())
    assert g.monsters[0].state == "hunting"


def test_a_cornered_badger_fights_back() -> None:
    rows = ["#####", "#<..#", "#####"]
    g = make_game(rows, [(BADGER, (3, 1), "fleeing")], ScriptedRng([face(1)] * 6))
    g.monsters[0].hp = 3
    events = g.submit(Move(1, 0))  # the player closes to (2,1): nowhere left to run
    assert g.monsters[0].pos == Pos(3, 1)
    assert any(isinstance(e, Attacked) and e.attacker == 1 for e in events)


def test_a_badger_that_stays_out_of_sight_twelve_turns_digs_away() -> None:
    rows = ["#" * 44, "#<" + "." * 41 + "#", "#" * 44]
    g = make_game(rows, [(BADGER, (6, 1), "fleeing")])
    g.monsters[0].hp = 3
    events = []
    for _ in range(40):
        events += g.submit(Wait())
        if not g.monsters:
            break
    assert Burrowed(1, "Gem Badger") in events and g.monsters == []


def test_a_badger_in_plain_view_does_not_burrow() -> None:
    rows = ["#####", "#<..#", "#####"]
    g = make_game(rows, [(BADGER, (3, 1), "fleeing")], ScriptedRng([face(1)] * 40))
    g.monsters[0].hp = 3
    for _ in range(15):
        g.submit(Wait())
    assert g.monsters != []


def test_a_rogue_can_backstab_a_fleeing_badger() -> None:
    rng = ScriptedRng([face(15), face(1), face(1), face(1)])
    g = make_game(HALL, [(BADGER, (2, 1), "fleeing", (1, 0))], rng, class_id="rogue")
    inert(g)
    hit = swings(g.submit(Move(1, 0)))[0]
    assert hit.backstab and hit.outcome is Outcome.HIT


def test_using_cleave_on_a_visible_eel_still_works() -> None:
    g = make_game(
        ["######", "#<~..#", "######"],
        [(EEL, (2, 1), "hunting")],
        ScriptedRng([face(15), face(1)]),
        rank=3,
    )
    g.monsters[0].ready_at = 10**9
    assert swings(g.submit(UseAbility()))
