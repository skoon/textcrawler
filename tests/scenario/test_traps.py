"""Trap spotting, stepping on traps, and the Rogue's Disarm, against the test Spring Trap."""

from minetoofar.core.geometry import Pos
from minetoofar.sim.events import (
    Blocked,
    BlockReason,
    Disarm,
    Move,
    Moved,
    PlayerDied,
    Refused,
    Run,
    StatusApplied,
    StubbornInvoked,
    TrapDisarmed,
    TrapSpotted,
    TrapTriggered,
    Wait,
)
from minetoofar.sim.game import Game
from minetoofar.sim.traps import Trap
from tests.helpers import MINER, ScriptedRng, make_game

HALL = ["#" * 14, "#<" + "." * 11 + "#", "#" * 14]
SPRING = "spring_trap"


def face(n: int) -> int:
    return n - 1


def hall(class_id: str, trap_x: int, rng: ScriptedRng | None = None) -> Game:
    return make_game(HALL, rng=rng, class_id=class_id, traps=[Trap(Pos(trap_x, 1), SPRING)])


# -- spotting ---------------------------------------------------------------------------------


def test_a_rogue_spots_hidden_traps_within_three_tiles_in_sight() -> None:
    g = hall("rogue", 5)  # four tiles away: not yet
    assert g.view().traps == ()
    events = g.submit(Move(1, 0))  # now three away
    assert TrapSpotted(Pos(5, 1), "Spring Trap") in events
    assert [t.pos for t in g.view().traps] == [Pos(5, 1)]


def test_a_rogue_spots_a_trap_that_starts_inside_the_radius() -> None:
    assert [t.pos for t in hall("rogue", 3).view().traps] == [Pos(3, 1)]


def test_a_rogue_cannot_spot_what_is_not_in_sight() -> None:
    rows = ["###########", "#<.+......#", "###########"]
    g = make_game(
        rows, class_id="rogue", traps=[Trap(Pos(4, 1), SPRING)]
    )  # three away, behind a door
    g.submit(Wait())
    assert g.view().traps == ()


def test_spotting_is_announced_once() -> None:
    g = hall("rogue", 5)
    seen = sum(isinstance(e, TrapSpotted) for _ in range(3) for e in g.submit(Move(1, 0)))
    assert seen == 1


def test_others_get_a_one_in_three_chance_each_turn_when_adjacent() -> None:
    g = hall("fighter", 2, ScriptedRng([1, 1, 0]))  # no, no, yes
    assert TrapSpotted(Pos(2, 1), "Spring Trap") not in g.submit(Wait())
    assert TrapSpotted(Pos(2, 1), "Spring Trap") not in g.submit(Wait())
    assert TrapSpotted(Pos(2, 1), "Spring Trap") in g.submit(Wait())


def test_others_never_roll_for_traps_that_are_not_adjacent() -> None:
    g = hall("fighter", 4, ScriptedRng([]))  # any draw would raise
    for _ in range(2):
        g.submit(Wait())
    assert g.view().traps == ()


def test_waiting_in_place_without_time_passing_does_not_reroll() -> None:
    g = hall("ranger", 2, ScriptedRng([1]))
    g.submit(Wait())
    g.submit(Move(-1, 0))  # a refused step: no time passes, so no second roll
    assert g.ticks == 100


# -- stepping on them -------------------------------------------------------------------------


def test_stepping_on_a_hidden_trap_springs_it_for_a_d6_after_the_hard_hat() -> None:
    g = hall("fighter", 2, ScriptedRng([face(4)]))  # 1d6+2 = 6, the Hard Hat takes 2 off
    events = g.submit(Move(1, 0))
    assert isinstance(events[0], Moved)
    assert TrapTriggered(Pos(2, 1), "Spring Trap", 4, "spring_trap") in events
    assert g.player.hp == 30 - 4
    assert g.traps == []  # a sprung trap is spent


def test_the_trigger_is_reported_and_stubborn_still_applies() -> None:
    g = hall("fighter", 2, ScriptedRng([face(6)]))
    g.player.hp = 5
    events = g.submit(Move(1, 0))
    assert TrapTriggered(Pos(2, 1), "Spring Trap", 6, "spring_trap") in events
    assert StubbornInvoked() in events and g.player.hp == 1


def test_a_trap_can_kill() -> None:
    g = hall("fighter", 2, ScriptedRng([face(6)]))
    g.player.hp, g.player.stubborn_used = 3, True
    events = g.submit(Move(1, 0))
    assert PlayerDied("Spring Trap") in events and g.dead and g.cause == "Spring Trap"


def test_armor_does_not_wear_from_traps() -> None:
    g = hall("fighter", 2, ScriptedRng([face(1)]))
    g.submit(Move(1, 0))
    assert g.player.body_dur == 18


def test_monsters_walk_over_traps_without_setting_them_off() -> None:
    rows = ["#########", "#<......#", "#########"]
    g = make_game(
        rows,
        [(MINER, (6, 1), "hunting")],
        ScriptedRng([face(1)] * 8),
        traps=[Trap(Pos(5, 1), SPRING)],
    )
    for _ in range(3):
        g.submit(Wait())
    assert len(g.traps) == 1 and g.monsters[0].pos.x < 5


# -- disarming --------------------------------------------------------------------------------


def test_a_rogue_disarms_an_adjacent_revealed_trap_in_one_action() -> None:
    g = hall("rogue", 2)
    assert [t.pos for t in g.view().traps] == [Pos(2, 1)]
    events = g.submit(Disarm(1, 0))
    assert events == [TrapDisarmed(Pos(2, 1), "Spring Trap")] and g.ticks == 100
    assert g.view().traps[0].disarmed


def test_a_disarmed_trap_never_triggers() -> None:
    g = hall("rogue", 2)
    g.submit(Disarm(1, 0))
    events = g.submit(Move(1, 0))
    assert not any(isinstance(e, TrapTriggered) for e in events) and g.player.hp == 22
    assert g.pos == Pos(2, 1)


def test_only_rogues_can_disarm() -> None:
    g = hall("fighter", 2, ScriptedRng([0]))
    g.submit(Wait())  # spotted
    assert g.submit(Disarm(1, 0)) == [Refused("not_rogue")] and g.ticks == 100


def test_disarming_needs_a_revealed_trap_in_that_direction() -> None:
    g = hall("rogue", 2)
    assert g.submit(Disarm(0, -1)) == [Refused("no_trap")]
    assert g.submit(Disarm(-1, 0)) == [Refused("no_trap")]
    assert g.ticks == 0


def test_a_hidden_trap_cannot_be_disarmed() -> None:
    rows = ["#########", "#<.+....#", "#########"]
    g = make_game(rows, class_id="rogue", traps=[Trap(Pos(4, 1), SPRING)])  # behind the door
    g.player.pos = Pos(3, 1)  # standing in the doorway, adjacent but never seen
    assert g.view().traps == ()
    assert g.submit(Disarm(1, 0)) == [Refused("no_trap")]


def test_state_hash_notices_a_revealed_trap() -> None:
    a, b = hall("fighter", 4), hall("fighter", 4)
    assert a.state_hash() == b.state_hash()
    b.traps[0].revealed = True
    assert a.state_hash() != b.state_hash()


# -- running -----------------------------------------------------------------------------------


def test_a_run_stops_when_a_trap_is_spotted_and_again_before_it() -> None:
    g = hall("rogue", 6)
    first = g.submit(Run(1, 0))
    assert any(isinstance(e, TrapSpotted) for e in first) and g.pos == Pos(3, 1)
    g.submit(Run(1, 0))
    assert g.pos == Pos(5, 1)  # one short of the trap
    assert g.player.hp == 22 and len(g.traps) == 1


def test_running_straight_at_a_revealed_trap_is_refused_outright() -> None:
    g = hall("rogue", 2)
    assert g.submit(Run(1, 0)) == [Blocked(Pos(2, 1), BlockReason.TRAP)]
    assert g.ticks == 0 and g.pos == Pos(1, 1)


def test_a_hidden_trap_does_not_stop_a_run() -> None:
    g = hall("fighter", 4, ScriptedRng([2, face(1)]))  # not noticed beside it; then d6 1
    events = g.submit(Run(1, 0))
    assert any(isinstance(e, TrapTriggered) for e in events) and g.pos == Pos(4, 1)


def test_a_plain_move_onto_a_revealed_trap_still_springs_it() -> None:
    g = hall("rogue", 2, ScriptedRng([face(5)]))
    g.submit(Move(1, 0))
    assert g.traps == [] and g.player.hp == 22 - 5


# -- the other two traps, and the Hard Hat -----------------------------------------------------


def trapped(kind: str, rng: ScriptedRng, class_id: str = "fighter") -> Game:
    return make_game(HALL, rng=rng, class_id=class_id, traps=[Trap(Pos(2, 1), kind)])


def test_a_tripwire_charge_drops_2d4_less_the_hard_hat() -> None:
    g = trapped("tripwire_charge", ScriptedRng([face(4), face(3)]))  # 4 + 3 = 7, less 2
    events = g.submit(Move(1, 0))
    assert TrapTriggered(Pos(2, 1), "Tripwire Charge", 5, "tripwire_charge") in events
    assert g.player.hp == 30 - 5


def test_the_hard_hat_never_takes_a_trap_below_one_damage() -> None:
    g = trapped("tripwire_charge", ScriptedRng([face(1), face(1)]))  # 2, less 2 would be 0
    g.submit(Move(1, 0))
    assert g.player.hp == 29


def test_a_stun_charge_stuns_for_a_turn_and_does_no_damage() -> None:
    g = trapped("stun_charge", ScriptedRng([]))  # no dice at all
    events = g.submit(Move(1, 0))
    assert TrapTriggered(Pos(2, 1), "Stun Charge", 0, "stun_charge") in events
    assert StatusApplied(0, "Hale", "stunned") in events
    assert g.player.hp == 30 and g.ticks == 200  # the step and the lost turn


def test_stun_charges_respect_the_stun_immunity() -> None:
    g = make_game(HALL, traps=[Trap(Pos(2, 1), "stun_charge"), Trap(Pos(3, 1), "stun_charge")])
    g.submit(Move(1, 0))
    events = g.submit(Move(1, 0))
    assert not any(isinstance(e, StatusApplied) for e in events)
