"""The pack: stacks by use charge, carry limits, and Standard Issue (GDD 8.2)."""

import pytest

from minetoofar.sim.actors import Item
from minetoofar.sim.items import add_item, carried, remove_one, standard_issue
from tests.helpers import DATA

KIT, TORCH = "patch_up_kit", "torch"


def test_stacks_merge_only_when_the_use_charge_matches() -> None:
    pack: list[Item] = []
    assert add_item(pack, DATA, Item(KIT, 1, 5))
    assert add_item(pack, DATA, Item(KIT, 1, 5))
    assert add_item(pack, DATA, Item(KIT, 1, 3))  # found stock bills differently
    assert pack == [Item(KIT, 2, 5), Item(KIT, 1, 3)]
    assert carried(pack, KIT) == 3


def test_the_carry_limit_counts_every_stack_of_that_item() -> None:
    pack = [Item(KIT, 3, 5)]
    assert add_item(pack, DATA, Item(KIT, 1, 0))  # 4 is the limit
    assert not add_item(pack, DATA, Item(KIT, 1, 5))
    assert not add_item(pack, DATA, Item(KIT, 1, 3))
    assert carried(pack, KIT) == 4
    assert pack == [Item(KIT, 3, 5), Item(KIT, 1, 0)]  # a refusal changes nothing


@pytest.mark.parametrize(
    ("item", "limit"),
    [("patch_up_kit", 4), ("torch", 3), ("overtime_fizz", 2), ("sanctified_detergent", 2)],
)
def test_carry_limits_follow_gdd_8_2(item: str, limit: int) -> None:
    pack: list[Item] = []
    for _ in range(limit):
        assert add_item(pack, DATA, Item(item, 1, 0))
    assert not add_item(pack, DATA, Item(item, 1, 0))


def test_a_bundle_that_would_overflow_is_refused_whole() -> None:
    pack = [Item(TORCH, 2, 0)]
    assert not add_item(pack, DATA, Item(TORCH, 2, 0))
    assert pack == [Item(TORCH, 2, 0)]


def test_equipment_is_never_limited_or_merged() -> None:
    pack: list[Item] = []
    for _ in range(6):
        assert add_item(pack, DATA, Item("boiler_suit", 1, 0, 9))
    assert len(pack) == 6 and all(i.qty == 1 and i.dur == 9 for i in pack)


def test_removing_one_takes_a_single_unit_with_its_charge() -> None:
    pack = [Item(KIT, 2, 5), Item(KIT, 1, 3)]
    assert remove_one(pack, 0) == Item(KIT, 1, 5)
    assert pack == [Item(KIT, 1, 5), Item(KIT, 1, 3)]
    assert remove_one(pack, 0) == Item(KIT, 1, 5)
    assert pack == [Item(KIT, 1, 3)]  # an empty stack disappears


def test_removing_a_missing_slot_fails_loudly() -> None:
    with pytest.raises(IndexError):
        remove_one([], 0)


def test_standard_issue_tops_up_to_two_kits_and_a_torch_at_list_price() -> None:
    pack: list[Item] = []
    standard_issue(pack, DATA, {KIT: 2, TORCH: 1})
    assert pack == [Item(KIT, 2, 5), Item(TORCH, 1, 2)]


def test_standard_issue_counts_what_you_already_carry_at_any_charge() -> None:
    pack = [Item(KIT, 1, 3), Item(TORCH, 2, 0)]
    standard_issue(pack, DATA, {KIT: 2, TORCH: 1})
    assert pack == [Item(KIT, 1, 3), Item(TORCH, 2, 0), Item(KIT, 1, 5)]


def test_standard_issue_adds_nothing_when_stocked() -> None:
    pack = [Item(KIT, 3, 0), Item(TORCH, 1, 0)]
    standard_issue(pack, DATA, {KIT: 2, TORCH: 1})
    assert pack == [Item(KIT, 3, 0), Item(TORCH, 1, 0)]
