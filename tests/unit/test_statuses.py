import pytest

from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.geometry import Pos
from minetoofar.sim.actors import Actor
from minetoofar.sim.statuses import (
    apply_status,
    cooldown_left,
    due_ticks,
    effective_cost,
    is_active,
    spend_charge,
    start_cooldown,
)

DEFS = load_gamedata().statuses


def actor(ready_at: int = 0) -> Actor:
    return Actor(id=1, name="Test", pos=Pos(0, 0), hp=10, max_hp=10, ready_at=ready_at)


def test_stun_delays_the_next_action_by_one_turn() -> None:
    a = actor(ready_at=500)
    assert apply_status(a, "stunned", now=500, defs=DEFS) is True
    assert a.ready_at == 600
    assert is_active(a, "stunned", 599) and not is_active(a, "stunned", 600)


def test_stun_is_followed_by_three_turns_of_immunity() -> None:
    a = actor()
    apply_status(a, "stunned", now=0, defs=DEFS)
    assert apply_status(a, "stunned", now=100, defs=DEFS) is False  # just ended
    assert apply_status(a, "stunned", now=399, defs=DEFS) is False  # still immune
    assert a.ready_at == 100  # refused applications delay nothing
    assert apply_status(a, "stunned", now=400, defs=DEFS) is True
    assert a.ready_at == 200


def test_overtime_scales_action_costs_down_to_sixty_percent() -> None:
    a = actor()
    assert effective_cost(a, 100, now=0, defs=DEFS) == 100
    apply_status(a, "overtime", now=0, defs=DEFS)
    assert effective_cost(a, 100, now=0, defs=DEFS) == 60
    assert effective_cost(a, 150, now=0, defs=DEFS) == 90
    assert effective_cost(a, 130, now=0, defs=DEFS) == 78  # floor of 78.0
    assert effective_cost(a, 50, now=0, defs=DEFS) == 30
    assert effective_cost(a, 101, now=0, defs=DEFS) == 60  # integer floor


def test_overtime_ends_when_its_duration_does() -> None:
    a = actor()
    apply_status(a, "overtime", now=0, defs=DEFS, duration=800)
    assert effective_cost(a, 100, now=799, defs=DEFS) == 60
    assert effective_cost(a, 100, now=800, defs=DEFS) == 100


def test_reapplying_overtime_refreshes_rather_than_stacks() -> None:
    a = actor()
    apply_status(a, "overtime", now=0, defs=DEFS)
    apply_status(a, "overtime", now=200, defs=DEFS)
    assert effective_cost(a, 100, now=200, defs=DEFS) == 60  # not 36
    assert is_active(a, "overtime", 499) and not is_active(a, "overtime", 500)


def test_stun_does_not_touch_action_costs() -> None:
    a = actor()
    apply_status(a, "stunned", now=0, defs=DEFS)
    assert effective_cost(a, 100, now=0, defs=DEFS) == 100


def test_unknown_status_fails_loudly() -> None:
    with pytest.raises(KeyError):
        apply_status(actor(), "nonesuch", now=0, defs=DEFS)


# -- Poisoned: damage ticks, refresh without stacking --------------------------------------


def test_poison_ticks_land_every_hundred_ticks_for_five_turns() -> None:
    a = actor()
    apply_status(a, "poisoned", now=0, defs=DEFS, power=2)
    assert due_ticks(a, "poisoned", now=99, defs=DEFS) == []
    assert due_ticks(a, "poisoned", now=100, defs=DEFS) == [2]
    assert due_ticks(a, "poisoned", now=100, defs=DEFS) == []  # already collected
    assert due_ticks(a, "poisoned", now=350, defs=DEFS) == [2, 2]  # ticks at 200 and 300
    assert is_active(a, "poisoned", 499)


def test_poison_ends_after_exactly_five_ticks_even_if_collected_late() -> None:
    a = actor()
    apply_status(a, "poisoned", now=0, defs=DEFS, power=2)
    assert due_ticks(a, "poisoned", now=900, defs=DEFS) == [2, 2, 2, 2, 2]
    assert not is_active(a, "poisoned", 900) and "poisoned" not in a.statuses


def test_reapplied_poison_refreshes_its_length_and_keeps_its_rhythm() -> None:
    a = actor()
    apply_status(a, "poisoned", now=0, defs=DEFS, power=2)
    due_ticks(a, "poisoned", now=250, defs=DEFS)  # ticks at 100 and 200 collected
    apply_status(a, "poisoned", now=250, defs=DEFS, power=3)  # refresh: ends at 750, power 3
    assert due_ticks(a, "poisoned", now=300, defs=DEFS) == [3]  # the next tick is still at 300
    assert due_ticks(a, "poisoned", now=2000, defs=DEFS) == [3, 3, 3, 3]  # 400, 500, 600, 700
    # (700 is the last tick before 750: refreshed to 500 ticks from 250, not stacked)


# -- Coated: charges, no time limit --------------------------------------------------------


def test_coated_lasts_until_its_charges_are_spent() -> None:
    a = actor()
    apply_status(a, "coated", now=0, defs=DEFS, power=2, charges=2)
    assert is_active(a, "coated", 10**9)
    assert spend_charge(a, "coated") == 2
    assert spend_charge(a, "coated") == 2
    assert not is_active(a, "coated", 0) and spend_charge(a, "coated") is None


def test_spending_a_charge_on_a_status_the_actor_lacks_gives_nothing() -> None:
    assert spend_charge(actor(), "coated") is None


# -- cooldowns are hidden statuses ---------------------------------------------------------


def test_cooldown_counts_down_and_clears() -> None:
    a = actor()
    assert cooldown_left(a, "cleave", now=0) == 0
    start_cooldown(a, "cleave", now=100, ticks=400)
    assert cooldown_left(a, "cleave", now=100) == 400
    assert cooldown_left(a, "cleave", now=350) == 150
    assert cooldown_left(a, "cleave", now=500) == 0 and cooldown_left(a, "cleave", now=999) == 0


def test_cooldowns_do_not_disturb_action_costs() -> None:
    a = actor()
    start_cooldown(a, "cleave", now=0, ticks=400)
    assert effective_cost(a, 100, now=0, defs=DEFS) == 100
