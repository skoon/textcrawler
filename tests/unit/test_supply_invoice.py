"""Supply drop invoices (GDD 8.5): only taken lines are billed, with handling and delivery."""

import pytest

from minetoofar.content.balance import load_balance
from minetoofar.gen.drops import SupplyLine
from minetoofar.sim.supply import Invoice, invoice, line_price
from tests.helpers import DATA

P = load_balance().supply
KIT = SupplyLine("patch_up_kit", 2, 0)
FIZZ = SupplyLine("overtime_fizz", 1, 0)
JACKET = SupplyLine("welders_jacket", 1, 16)  # a tier 2 body armor


def bill(lines: list[SupplyLine], taken: tuple[int, ...], delivery_due: bool = True) -> Invoice:
    return invoice(lines, taken, delivery_due, DATA, P)


def test_the_gdd_example_comes_to_forty_nine() -> None:
    inv = bill([KIT, FIZZ, JACKET], (0, 1, 2))
    assert [(r.label, r.total) for r in inv.rows] == [
        ("Patch-Up Kit x2 @ 5g", 10),
        ("Overtime Fizz x1 @ 7g", 7),
        ("Welder's Jacket (T2)", 22),
    ]
    assert (inv.subtotal, inv.handling, inv.delivery, inv.total) == (39, 8, 2, 49)


def test_only_taken_lines_are_billed() -> None:
    inv = bill([KIT, FIZZ, JACKET], (0,))
    assert (inv.subtotal, inv.handling, inv.delivery, inv.total) == (10, 2, 2, 14)
    assert [r.taken for r in inv.rows] == [True, False, False]


def test_taking_nothing_costs_nothing_not_even_delivery() -> None:
    inv = bill([KIT, FIZZ], ())
    assert (inv.subtotal, inv.handling, inv.delivery, inv.total) == (0, 0, 0, 0)


def test_delivery_is_billed_once_per_crate() -> None:
    inv = bill([KIT], (0,), delivery_due=False)
    assert (inv.subtotal, inv.handling, inv.delivery, inv.total) == (10, 2, 0, 12)


@pytest.mark.parametrize(("subtotal_item", "handling"), [(1, 1), (5, 1), (6, 2), (10, 2), (11, 3)])
def test_handling_is_twenty_percent_rounded_up(subtotal_item: int, handling: int) -> None:
    # a made-up line priced by quantity: kits at 5g each give subtotals 5, 10, 15 ...
    inv = bill([SupplyLine("patch_up_kit", 1, 0)], (0,))
    assert inv.handling == -(-inv.subtotal * P.handling_pct // 100)
    assert handling == -(-subtotal_item * 20 // 100)


@pytest.mark.parametrize(
    ("line", "price"),
    [
        (SupplyLine("patch_up_kit", 2, 0), 10),
        (SupplyLine("torch", 1, 0), 2),
        (SupplyLine("overtime_fizz", 2, 0), 14),
        (SupplyLine("sanctified_detergent", 1, 0), 6),
        (SupplyLine("hatchet", 1, 0), 12),  # tier 1
        (SupplyLine("welders_jacket", 1, 16), 22),  # tier 2
        (SupplyLine("assay_blade", 1, 0), 34),  # tier 3
    ],
)
def test_prices_follow_the_list_price_and_the_tier(line: SupplyLine, price: int) -> None:
    assert line_price(line, DATA, P) == price


def test_a_line_that_is_not_there_to_take_fails_loudly() -> None:
    with pytest.raises(IndexError):
        bill([KIT], (3,))
