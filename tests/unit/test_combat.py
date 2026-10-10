"""GDD 7.2, enumerated over all twenty die faces instead of sampled."""

import pytest

from minetoofar.sim.combat import (
    AttackResult,
    Outcome,
    Stats,
    apply_dr,
    hit_faces,
    hit_outcome,
    resolve_attack,
    roll_damage,
)
from tests.helpers import ScriptedRng


def pct(atk: int, defense: int, situational: int = 0) -> int:
    return hit_faces(atk, defense, situational) * 100 // 20


def test_natural_one_always_misses_and_natural_twenty_always_crits() -> None:
    assert hit_outcome(1, atk=50, defense=0) is Outcome.MISS
    assert hit_outcome(20, atk=-50, defense=50) is Outcome.CRIT


def test_hit_needs_roll_plus_atk_to_reach_ten_plus_def() -> None:
    assert hit_outcome(4, atk=5, defense=0) is Outcome.MISS  # 9 < 10
    assert hit_outcome(5, atk=5, defense=0) is Outcome.HIT  # 10 >= 10
    assert hit_outcome(19, atk=0, defense=10) is Outcome.MISS  # 19 < 20
    assert hit_outcome(10, atk=0, defense=0) is Outcome.HIT


def test_gdd_reference_numbers_at_rank_one() -> None:
    assert pct(atk=5, defense=0) == 80  # Fighter or Rogue hits a Miner
    assert pct(atk=3, defense=0) == 70  # Ranger main hand
    assert pct(atk=2, defense=1) == 60  # Miner hits the Fighter
    assert pct(atk=2, defense=2) == 55  # ... the Ranger
    assert pct(atk=2, defense=5) == 40  # ... the Rogue


def test_the_only_certain_hit_is_a_critical_and_it_is_one_face_in_twenty() -> None:
    crits = [r for r in range(1, 21) if hit_outcome(r, atk=99, defense=0) is Outcome.CRIT]
    assert crits == [20]
    assert hit_faces(99, 0) == 19  # every face but the natural one


def test_even_a_hopeless_attack_hits_on_a_natural_twenty() -> None:
    assert hit_faces(atk=-30, defense=30) == 1


def test_flanking_bonus_is_a_situational_modifier() -> None:
    assert pct(atk=5, defense=0, situational=2) == 90
    assert pct(atk=5, defense=0, situational=-2) == 70


def test_damage_adds_dice_and_flat_bonus() -> None:
    fighter = Stats(atk=5, defense=1, dr=2, dice_n=1, dice_sides=8, dmg_flat=3, attack_cost=100)
    assert roll_damage(ScriptedRng([4]), fighter, crit=False) == 5 + 3  # d8 face 5


def test_a_critical_doubles_the_dice_not_the_flat_bonus() -> None:
    fighter = Stats(atk=5, defense=1, dr=2, dice_n=1, dice_sides=8, dmg_flat=3, attack_cost=100)
    rng = ScriptedRng([4, 7])  # faces 5 and 8
    assert roll_damage(rng, fighter, crit=True) == 5 + 8 + 3
    assert rng.queue == []


@pytest.mark.parametrize(("raw", "dr", "result"), [(10, 2, 8), (3, 3, 1), (3, 9, 1), (1, 0, 1)])
def test_damage_reduction_never_takes_a_hit_below_one(raw: int, dr: int, result: int) -> None:
    assert apply_dr(raw, dr) == result


def test_resolve_attack_miss_spends_only_the_attack_roll() -> None:
    rng = ScriptedRng([0])  # natural 1
    stats = Stats(atk=5, defense=0, dr=0, dice_n=1, dice_sides=8, dmg_flat=3, attack_cost=100)
    assert resolve_attack(rng, stats, stats) == AttackResult(1, Outcome.MISS, 0)


def test_resolve_attack_hit_rolls_damage_then_subtracts_dr() -> None:
    attacker = Stats(atk=5, defense=1, dr=2, dice_n=1, dice_sides=8, dmg_flat=3, attack_cost=100)
    miner = Stats(atk=2, defense=0, dr=1, dice_n=1, dice_sides=6, dmg_flat=1, attack_cost=100)
    rng = ScriptedRng([9, 5])  # d20 face 10, d8 face 6
    assert resolve_attack(rng, attacker, miner) == AttackResult(10, Outcome.HIT, 6 + 3 - 1)


def test_resolve_attack_critical_uses_double_dice() -> None:
    attacker = Stats(atk=5, defense=1, dr=2, dice_n=1, dice_sides=8, dmg_flat=3, attack_cost=100)
    miner = Stats(atk=2, defense=0, dr=0, dice_n=1, dice_sides=6, dmg_flat=1, attack_cost=100)
    rng = ScriptedRng([19, 0, 0])  # natural 20, then two d8 ones
    assert resolve_attack(rng, attacker, miner) == AttackResult(20, Outcome.CRIT, 1 + 1 + 3)


def test_situational_modifier_can_turn_a_miss_into_a_hit() -> None:
    a = Stats(atk=5, defense=0, dr=0, dice_n=1, dice_sides=4, dmg_flat=0, attack_cost=100)
    d = Stats(atk=0, defense=0, dr=0, dice_n=1, dice_sides=4, dmg_flat=0, attack_cost=100)
    assert resolve_attack(ScriptedRng([3]), a, d).outcome is Outcome.MISS  # face 4: 4+5 < 10
    assert resolve_attack(ScriptedRng([3, 0]), a, d, situational=2).outcome is Outcome.HIT


FIGHTER = Stats(atk=5, defense=1, dr=2, dice_n=1, dice_sides=8, dmg_flat=3, attack_cost=100)
TARGET = Stats(atk=0, defense=0, dr=0, dice_n=1, dice_sides=4, dmg_flat=0, attack_cost=100)


def test_an_automatic_hit_lands_even_on_a_natural_one_but_still_spends_the_roll() -> None:
    rng = ScriptedRng([0, 3])  # face 1, then d8 face 4
    result = resolve_attack(rng, FIGHTER, TARGET, auto_hit=True)
    assert result == AttackResult(1, Outcome.HIT, 4 + 3)
    assert rng.queue == []


def test_an_automatic_hit_is_still_a_critical_on_a_natural_twenty() -> None:
    result = resolve_attack(ScriptedRng([19, 0, 0]), FIGHTER, TARGET, auto_hit=True)
    assert result.outcome is Outcome.CRIT and result.damage == 1 + 1 + 3


def test_bonus_dice_roll_after_the_weapon_dice_and_are_not_doubled_by_a_crit() -> None:
    # critical: weapon 2d8 (faces 2, 3) then backstab 2d4 (faces 4, 4), then +3
    rng = ScriptedRng([19, 1, 2, 3, 3])
    result = resolve_attack(rng, FIGHTER, TARGET, bonus_dice=(2, 4))
    assert result.damage == 2 + 3 + 4 + 4 + 3 and rng.queue == []


def test_bonus_flat_adds_once_and_dr_still_applies_to_the_total() -> None:
    armored = Stats(atk=0, defense=0, dr=3, dice_n=1, dice_sides=4, dmg_flat=0, attack_cost=100)
    result = resolve_attack(ScriptedRng([14, 3]), FIGHTER, armored, bonus_flat=2)
    assert result.damage == 4 + 3 + 2 - 3


def test_a_miss_ignores_every_bonus() -> None:
    rng = ScriptedRng([0])
    assert resolve_attack(rng, FIGHTER, TARGET, bonus_dice=(2, 4), bonus_flat=5).damage == 0
    assert rng.queue == []
