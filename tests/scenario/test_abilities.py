"""Cleave, Poison Blades, Dual Strike, and the cooldowns that gate them (GDD 6.6)."""

from dataclasses import replace

from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import (
    AbilityUsed,
    Attacked,
    Killed,
    Move,
    PoisonTick,
    Refused,
    StatusApplied,
    UseAbility,
    Wait,
)
from minetoofar.sim.game import Game
from tests.helpers import MINER, ScriptedRng, inert, make_game

ROOM = ["#######", "#.....#", "#.....#", "#..<..#", "#.....#", "#.....#", "#######"]  # player (3,3)
N, E, S = (3, 2), (4, 3), (3, 4)


def face(n: int) -> int:
    return n - 1


def swings(events: list[object]) -> list[Attacked]:
    return [e for e in events if isinstance(e, Attacked)]


def surrounded(class_id: str, rank: int, rng: ScriptedRng, spots: list[tuple[int, int]]) -> Game:
    g = make_game(ROOM, [(MINER, p, "hunting") for p in spots], rng, rank=rank, class_id=class_id)
    return inert(g)


# -- Cleave -----------------------------------------------------------------------------------


def test_cleave_hits_every_adjacent_enemy_once_at_minus_two_in_one_action() -> None:
    # Rank 3 Fighter: ATK +6, so a 4 normally hits; at -2 it needs a 6. Order: N, E, S.
    rng = ScriptedRng([face(6), face(2), face(5), face(20), face(1), face(1)])
    g = surrounded("fighter", 3, rng, [N, E, S])
    events = g.submit(UseAbility())
    assert events[0] == AbilityUsed("Cleave")
    first, second, third = swings(events)
    assert (first.outcome, first.damage) == (Outcome.HIT, 2 + 3)
    assert second.outcome is Outcome.MISS  # a 5 + 6 - 2 = 9 falls short
    assert third.outcome is Outcome.CRIT and third.damage == 1 + 1 + 3
    assert g.ticks == 100 and rng.queue == []


def test_cleave_rolls_damage_separately_and_can_kill_several() -> None:
    rng = ScriptedRng([face(10), face(8), face(10), face(8)])
    g = surrounded("fighter", 3, rng, [N, S])
    for m in g.monsters:
        m.hp = 5
    events = g.submit(UseAbility())
    assert [type(e) for e in events].count(Killed) == 2 and g.monsters == []


def test_cleave_waits_four_turns_before_it_can_be_used_again() -> None:
    rng = ScriptedRng([face(15), face(3), face(15), face(3)])
    g = surrounded("fighter", 3, rng, [N])
    g.monsters[0].hp = 500
    g.submit(UseAbility())
    assert g.submit(UseAbility()) == [Refused("cooldown")] and g.ticks == 100
    g.submit(Wait())
    g.submit(Wait())
    assert g.submit(UseAbility()) == [Refused("cooldown")]  # 300 of 400 ticks gone
    g.submit(Wait())
    assert isinstance(g.submit(UseAbility())[0], AbilityUsed)  # exactly 400 later


def test_rank_five_cleave_loses_the_penalty_and_cools_down_in_three_turns() -> None:
    rng = ScriptedRng([face(4), face(1), face(15), face(1)])
    g = surrounded("fighter", 5, rng, [N])  # ATK +6: a 4 hits only with no penalty
    g.monsters[0].hp = 500
    assert swings(g.submit(UseAbility()))[0].outcome is Outcome.HIT
    g.submit(Wait())
    g.submit(Wait())
    assert isinstance(g.submit(UseAbility())[0], AbilityUsed)  # 300 ticks later


def test_cleave_with_nobody_adjacent_costs_nothing_and_does_not_start_the_cooldown() -> None:
    g = make_game(ROOM, rank=3)
    assert g.submit(UseAbility()) == [Refused("no_target")]
    assert g.ticks == 0 and g.view().hero.ability.ready


def test_cleave_cannot_reach_around_a_corner() -> None:
    rows = ["#####", "#.#.#", "#.<.#", "#####"]
    g = inert(
        make_game(rows, [(MINER, (3, 1), "hunting")], rank=3)
    )  # diagonal past the wall at (2,1)
    assert g.submit(UseAbility()) == [Refused("no_target")]


def test_abilities_wait_for_rank_three() -> None:
    for class_id in ("fighter", "rogue", "ranger"):
        g = make_game(ROOM, [(MINER, N, "hunting")], rank=2, class_id=class_id)
        assert g.submit(UseAbility()) == [Refused("locked")], class_id
        assert g.ticks == 0


# -- Poison Blades -------------------------------------------------------------------------------


def test_poison_blades_coats_the_weapons_for_five_hits() -> None:
    g = make_game(ROOM, rank=3, class_id="rogue")
    events = g.submit(UseAbility())
    assert events == [AbilityUsed("Poison Blades")] and g.ticks == 100
    coat = g.player.statuses["coated"]
    assert (coat.charges, coat.power) == (5, 2)
    assert g.submit(UseAbility()) == [Refused("cooldown")]


def test_each_weapon_hit_spends_a_charge_and_poisons_the_target() -> None:
    rng = ScriptedRng([face(15), face(3)])
    g = inert(make_game(ROOM, [(MINER, N, "hunting")], rng, rank=3, class_id="rogue"))
    g.monsters[0].hp = 500
    g.submit(UseAbility())
    events = g.submit(Move(0, -1))
    assert StatusApplied(1, "Shambling Miner", "poisoned") in events
    assert g.player.statuses["coated"].charges == 4
    assert g.monsters[0].statuses["poisoned"].power == 2


def test_a_miss_keeps_the_charge() -> None:
    g = inert(
        make_game(ROOM, [(MINER, N, "hunting")], ScriptedRng([face(1)]), rank=3, class_id="rogue")
    )
    g.submit(UseAbility())
    g.submit(Move(0, -1))
    assert g.player.statuses["coated"].charges == 5 and "poisoned" not in g.monsters[0].statuses


def test_the_sixth_hit_is_clean() -> None:
    rng = ScriptedRng([face(15), face(1)] * 6)
    g = inert(make_game(ROOM, [(MINER, N, "hunting")], rng, rank=3, class_id="rogue"))
    g.monsters[0].hp = 500
    g.submit(UseAbility())
    applied = 0
    for _ in range(6):
        applied += sum(isinstance(e, StatusApplied) for e in g.submit(Move(0, -1)))
    assert applied == 5 and "coated" not in g.player.statuses


def test_poison_ticks_every_turn_and_eventually_kills() -> None:
    # t=0 the Miner swings (miss); the Rogue hits for 3+3=6 at t=100 and poisons it (ticks at
    # 200, 300, 400...); the Miner keeps swinging (misses) until the poison finishes it
    rng = ScriptedRng([face(1), face(15), face(3), face(1), face(1), face(1)])
    g = make_game(ROOM, [(MINER, N, "hunting")], rng, rank=3, class_id="rogue")
    g.submit(UseAbility())
    g.submit(Move(0, -1))
    assert g.monsters[0].hp == 6
    g.submit(Wait())
    assert g.monsters[0].hp == 4  # the tick at 200
    log: list[object] = []
    log += g.submit(Wait())
    assert g.monsters[0].hp == 2 and PoisonTick(1, "Shambling Miner", 2) in log
    log = g.submit(Wait())
    assert g.monsters == [] and Killed(1, "Shambling Miner") in log


def test_poison_ignores_damage_reduction() -> None:
    rng = ScriptedRng([face(15), face(3), face(1), face(1)])  # the hit; then two swings that miss
    g = make_game(ROOM, [(MINER, N, "hunting")], rng, rank=3, class_id="rogue")
    g.monsters[0].stats = replace(g.monsters[0].stats, dr=5)
    g.monsters[0].ready_at = 150  # it first acts after the Rogue has struck
    g.submit(UseAbility())
    g.submit(Move(0, -1))  # 3 + 3 = 6, less DR 5: one point
    assert g.monsters[0].hp == 11
    g.submit(Wait())  # the Miner's turn at 250 collects the tick due at 200
    assert g.monsters[0].hp == 9  # the full 2 despite DR 5


def test_rank_five_poison_is_stronger_and_lasts_six_hits() -> None:
    g = make_game(ROOM, rank=5, class_id="rogue")
    g.submit(UseAbility())
    coat = g.player.statuses["coated"]
    assert (coat.charges, coat.power) == (6, 3)


def test_poison_blades_cool_down_over_thirty_turns() -> None:
    g = inert(make_game(ROOM, rank=3, class_id="rogue"))
    g.submit(UseAbility())
    for _ in range(28):
        g.submit(Wait())
    assert g.submit(UseAbility()) == [Refused("cooldown")]  # 2900 ticks
    g.submit(Wait())
    assert isinstance(g.submit(UseAbility())[0], AbilityUsed)  # 3000


# -- Dual Strike -------------------------------------------------------------------------------


def test_dual_strike_swings_both_hatchets_at_full_attack_and_adds_damage() -> None:
    # Rank 3 Ranger: ATK +4 main, +4 off hand (normally 0): a 6 hits with both
    rng = ScriptedRng([face(6), face(2), face(6), face(3)])
    g = surrounded("ranger", 3, rng, [N])
    g.monsters[0].hp = 40
    main, off = swings(g.submit(UseAbility()))
    assert (main.outcome, main.damage) == (Outcome.HIT, 2 + 1 + 1)  # d6 + STR 1 + bonus 1
    assert (off.outcome, off.damage) == (Outcome.HIT, 3 + 0 + 1)  # no strength, bonus 1
    assert g.ticks == 100


def test_dual_strike_cools_down_in_five_turns_or_three_at_rank_five() -> None:
    g = surrounded("ranger", 3, ScriptedRng([face(15), face(1)] * 6), [N])
    g.monsters[0].hp = 500
    g.submit(UseAbility())
    for _ in range(3):
        g.submit(Wait())
    assert g.submit(UseAbility()) == [Refused("cooldown")]  # 400 of 500
    g.submit(Wait())
    assert isinstance(g.submit(UseAbility())[0], AbilityUsed)
    g5 = surrounded("ranger", 5, ScriptedRng([face(15), face(1)] * 4), [N])
    g5.monsters[0].hp = 500
    first = swings(g5.submit(UseAbility()))
    assert first[0].damage == 1 + 1 + 1 + 2  # d6 1, STR 1, Rank bonus 1, Dual Strike +2
    g5.submit(Wait())
    g5.submit(Wait())
    assert isinstance(g5.submit(UseAbility())[0], AbilityUsed)  # 300 ticks later


def test_dual_strike_picks_the_first_adjacent_enemy_clockwise_from_north() -> None:
    rng = ScriptedRng([face(15), face(1), face(15), face(1)])
    g = surrounded("ranger", 3, rng, [S, E])
    g.monsters[0].hp = g.monsters[1].hp = 500
    targets = {e.target for e in swings(g.submit(UseAbility()))}
    assert targets == {2}  # the Miner at (4,3) is east: before south in compass order


def test_dual_strike_needs_someone_beside_you() -> None:
    g = make_game(ROOM, rank=3, class_id="ranger")
    assert g.submit(UseAbility()) == [Refused("no_target")]
