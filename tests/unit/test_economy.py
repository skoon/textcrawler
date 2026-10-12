"""The pay slip (GDD 8.6, 8.8): worked examples, every line, waivers, debt, and invariants."""

from dataclasses import replace

import pytest

from minetoofar.content.balance import load_balance
from minetoofar.core.rng import Rng
from minetoofar.sim.economy import (
    Account,
    Choices,
    Slip,
    compute_slip,
    score,
    title_key,
)
from minetoofar.sim.ledger import Ledger, Repair, Salvage, Use

# The worked examples are the GDD's own figures, written when the Base Job Fee was 15g. Balance
# tuning (M9) lowered the shipped fee; the arithmetic is checked here at the GDD's number.
GDD_BASE_FEE = 15
E = replace(load_balance().economy, base_fee=GDD_BASE_FEE)
NUGGET = ("silver_nugget", "Silver Nugget", 2)
GEM = ("rough_gem", "Rough Gem", 4)
KIT = ("patch_up_kit", "Patch-Up Kit")
TORCH = ("torch", "Torch")


def ledger(**fields: object) -> Ledger:
    return replace(Ledger(level=2), **fields)  # type: ignore[arg-type]


def salvage(*items: tuple[str, str, int, int]) -> list[Salvage]:
    return [Salvage(*i) for i in items]


def slip(led: Ledger, account: Account | None = None, choices: Choices | None = None) -> Slip:
    return compute_slip(led, account or Account(), choices or Choices(), E)


def amounts(lines: tuple[object, ...]) -> dict[str, int]:
    return {line.key: line.owed for line in lines}  # type: ignore[attr-defined]


# -- GDD 8.6 worked examples -------------------------------------------------------------------


def test_worked_example_1_the_slip_in_section_5_2() -> None:
    led = ledger(
        salvage=salvage((*NUGGET, 2), (*GEM, 1)),
        repair=Repair("Boiler Suit", 8, 3),
        used=[Use(*KIT, 5, 1), Use(*KIT, 3, 1), Use(*TORCH, 2, 1)],
        stubborn=True,
        clock_ins=1,
    )
    s = slip(led)
    assert s.gross == 23  # 15 + 4 + 4
    assert [(line.label, line.owed) for line in s.gross_lines] == [
        ("Base Job Fee", 15),
        ("Salvage Credit: Silver Nugget x2 @2g", 4),
        ("Salvage Credit: Rough Gem x1 @4g", 4),
    ]
    assert amounts(s.adjustments) == {
        "repair": 6,  # ceil(8 * 3 / 4)
        "used:patch_up_kit:5": 5,
        "used:patch_up_kit:3": 3,
        "used:torch:2": 2,
        "hazard_pay": 5,
        "timecard": 1,
    }
    assert s.adjusted == 22 and s.net == 1
    assert (s.wallet_before, s.wallet_after, s.debt_after) == (0, 1, 0)


def test_worked_example_2_a_graveyard_floor_in_deficit() -> None:
    led = ledger(
        level=3,
        graveyard=True,
        salvage=salvage((*NUGGET, 1)),
        repair=Repair("Boiler Suit", 9, 3),
        used=[Use(*KIT, 5, 2), Use(*KIT, 3, 1), Use(*TORCH, 2, 1)],
        torches_dropped=1,
        traps=1,
        stubborn=True,
    )
    s = slip(led, Account(wallet=1))
    assert s.gross == 22  # 15 + 5 + 2
    assert amounts(s.adjustments) == {
        "repair": 7,  # ceil(9 * 3 / 4)
        "used:patch_up_kit:5": 10,
        "used:patch_up_kit:3": 3,
        "used:torch:2": 2,
        "torch_dropped": 2,
        "hazard_surcharge": 3,
        "hazard_pay": 5,
    }
    assert s.adjusted == 32 and s.net == -10
    assert (s.wallet_after, s.debt_after) == (0, 9)  # the wallet pays 1; debt 9


def test_worked_example_3_the_following_slip_opens_with_the_debt() -> None:
    account = Account(debt=9)
    s = slip(ledger(level=4, salvage=salvage((*NUGGET, 5))), account)
    assert amounts(s.adjustments) == {"carried": 9, "late_fee": 1}  # ceil(9 * 10 / 100)
    assert s.adjusted == 10 and s.gross == 25 and s.net == 15
    assert (s.wallet_after, s.debt_after) == (15, 0)  # a strong level clears it


def test_worked_example_3_a_weak_level_deepens_the_hole() -> None:
    led = ledger(level=4, repair=Repair("Boiler Suit", 12, 3), used=[Use(*KIT, 5, 3)])
    s = slip(led, Account(debt=9))
    assert s.gross == 15 and s.adjusted == 9 + 1 + 9 + 15  # carried, late fee, repair, kits
    assert s.net == -19 and (s.wallet_after, s.debt_after) == (0, 19)


# -- gross pay ---------------------------------------------------------------------------------


def test_a_quiet_level_pays_the_base_fee_only() -> None:
    s = slip(ledger())
    assert s.gross == 15 and s.adjusted == 0 and s.net == 15


def test_a_graveyard_floor_pays_the_hazard_premium() -> None:
    s = slip(ledger(graveyard=True))
    assert s.gross == 20 and s.gross_lines[1].label == "Hazard Premium"


def test_a_defeated_rogue_human_pays_the_bounty() -> None:
    s = slip(ledger(bounty=True))
    assert s.gross == 21 and s.gross_lines[1].label == "Unauthorized Personnel Retrieval Bounty"


# -- armor repair ------------------------------------------------------------------------------


# points missing 0, 1, 3, 4, 5 at repair rates 1-4 (quarter-gold per point, rounded up)
REPAIR_BILLS = {1: (0, 1, 1, 1, 2), 2: (0, 1, 2, 2, 3), 3: (0, 1, 3, 3, 4), 4: (0, 1, 3, 4, 5)}


@pytest.mark.parametrize("rate", [1, 2, 3, 4])
def test_repair_rounds_up_in_quarter_gold_at_every_rate(rate: int) -> None:
    for missing, want in zip((0, 1, 3, 4, 5), REPAIR_BILLS[rate], strict=True):
        s = slip(ledger(repair=Repair("Vest", missing, rate)))
        assert amounts(s.adjustments).get("repair", 0) == want, (missing, rate)


def test_declining_repair_leaves_the_bill_off() -> None:
    s = slip(ledger(repair=Repair("Boiler Suit", 8, 3)), choices=Choices(repair=False))
    assert "repair" not in amounts(s.adjustments) and s.repaired is False


def test_repair_is_billed_and_flagged_when_taken() -> None:
    assert slip(ledger(repair=Repair("Boiler Suit", 8, 3))).repaired is True
    assert slip(ledger(repair=Repair("Boiler Suit", 0, 3))).repaired is False  # nothing to fix


# -- consumables -------------------------------------------------------------------------------


def test_each_used_stack_is_its_own_line_at_its_own_use_charge() -> None:
    used = [Use(*KIT, 5, 2), Use(*KIT, 3, 1), Use(*KIT, 0, 4)]  # issued, found, prepaid
    s = slip(ledger(used=used))
    lines = {line.key: (line.label, line.owed) for line in s.adjustments}
    assert lines["used:patch_up_kit:5"] == ("Consumables: Patch-Up Kit x2 @5g", 10)
    assert lines["used:patch_up_kit:3"] == ("Consumables: Patch-Up Kit x1 @3g", 3)
    assert lines["used:patch_up_kit:0"] == ("Consumables: Patch-Up Kit x4 @0g (prepaid)", 0)


# -- incidents ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "want"),
    [
        ({"traps": 2}, {"hazard_surcharge": 6}),
        ({"traps": 2, "tripwires": 1}, {"hazard_surcharge": 6, "shoring": 4}),
        ({"torches_dropped": 2}, {"torch_dropped": 4}),
        ({"stubborn": True}, {"hazard_pay": 5}),
        ({"clock_ins": 3}, {"timecard": 3}),
    ],
)
def test_each_incident_has_its_own_line(fields: dict[str, object], want: dict[str, int]) -> None:
    assert amounts(slip(ledger(**fields)).adjustments) == want


@pytest.mark.parametrize(("n", "billed"), [(1, 1), (4, 4), (5, 5), (6, 5), (40, 5)])
def test_the_timecard_irregularity_is_capped_per_level(n: int, billed: int) -> None:
    assert amounts(slip(ledger(clock_ins=n)).adjustments) == {"timecard": billed}


def test_supply_drop_charges_pass_straight_through() -> None:
    s = slip(ledger(supply=[("Supply Drop Invoice #1", 39)]))
    assert amounts(s.adjustments) == {"supply:1": 39}


# -- waivers and coupons, in the fixed order ---------------------------------------------------

BUSY = dict(  # noqa: C408
    repair=Repair("Boiler Suit", 8, 3),  # 6
    traps=1, tripwires=1,  # surcharge 3, shoring 4
    torches_dropped=1,  # 2
    clock_ins=2,  # 2
    stubborn=True,  # 5
)  # fmt: skip


def busy() -> Ledger:
    return ledger(**BUSY)


def test_the_busy_level_without_waivers() -> None:
    s = slip(busy())
    assert amounts(s.adjustments) == {
        "repair": 6, "torch_dropped": 2, "hazard_surcharge": 3, "shoring": 4,
        "hazard_pay": 5, "timecard": 2,
    }  # fmt: skip
    assert s.adjusted == 22


def test_a_repair_plan_halves_the_repair_line_rounded_up() -> None:
    s = slip(busy(), Account(repair_plan=True))
    assert amounts(s.adjustments)["repair"] == 3
    s = slip(ledger(repair=Repair("Vest", 3, 3)), Account(repair_plan=True))  # ceil(9/4) = 3 -> 2
    assert amounts(s.adjustments)["repair"] == 2
    assert s.account.repair_plan is False  # used up


def test_a_repair_plan_waits_for_a_repair_line() -> None:
    s = slip(ledger(), Account(repair_plan=True))
    assert s.account.repair_plan is True
    s = slip(busy(), Account(repair_plan=True), Choices(repair=False))
    assert s.account.repair_plan is True  # declining repair does not use the plan up


def test_a_hazard_waiver_zeroes_the_surcharge_and_shoring_only() -> None:
    s = slip(busy(), Account(hazard_waiver=True))
    got = amounts(s.adjustments)
    assert got["hazard_surcharge"] == 0 and got["shoring"] == 0
    assert got["torch_dropped"] == 2 and got["timecard"] == 2 and got["hazard_pay"] == 5
    assert s.account.hazard_waiver is False


def test_a_property_damage_waiver_covers_incidentals_up_to_six_never_hazard_pay() -> None:
    s = slip(busy(), Account(damage_waiver=True))
    got = amounts(s.adjustments)
    # incidentals in slip order: torch 2, surcharge 3, shoring 4, timecard 2 -> 6g forgiven
    assert got["torch_dropped"] == 0 and got["hazard_surcharge"] == 0
    assert got["shoring"] == 3 and got["timecard"] == 2 and got["hazard_pay"] == 5
    assert s.account.damage_waiver is False


def test_the_waivers_apply_in_the_fixed_order() -> None:
    account = Account(repair_plan=True, hazard_waiver=True, damage_waiver=True)
    s = slip(busy(), account)
    got = amounts(s.adjustments)
    # repair 6 -> 3; hazard waiver zeroes 3 + 4; the damage waiver then has 6g for 2 + 2
    assert got == {
        "repair": 3, "torch_dropped": 0, "hazard_surcharge": 0, "shoring": 0,
        "hazard_pay": 5, "timecard": 0,
    }  # fmt: skip


def test_a_waived_line_remembers_what_waived_it() -> None:
    s = slip(busy(), Account(hazard_waiver=True))
    line = next(line for line in s.adjustments if line.key == "shoring")
    assert line.amount == 4 and line.waivers == (("Hazard Waiver", 4),)


@pytest.mark.parametrize(("clock_ins", "owed"), [(1, 0), (2, 0), (3, 0), (4, 4), (5, 5)])
def test_the_lanyard_threshold_is_three_inclusive(clock_ins: int, owed: int) -> None:
    led = ledger(clock_ins=clock_ins, lanyard=True)
    assert amounts(slip(led).adjustments) == {"timecard": owed}


def test_the_lanyard_takes_only_the_first_small_line() -> None:
    led = ledger(torches_dropped=1, clock_ins=1, lanyard=True)
    assert amounts(slip(led).adjustments) == {"torch_dropped": 0, "timecard": 1}
    led = ledger(traps=1, tripwires=1, lanyard=True)  # surcharge 3 goes; shoring 4 is too big
    assert amounts(slip(led).adjustments) == {"hazard_surcharge": 0, "shoring": 4}


def test_the_lanyard_skips_lines_already_waived_and_never_touches_hazard_pay() -> None:
    led = ledger(traps=1, clock_ins=2, lanyard=True)  # surcharge 3, timecard 2
    s = slip(led, Account(hazard_waiver=True))
    assert amounts(s.adjustments) == {"hazard_surcharge": 0, "timecard": 0}
    s = slip(ledger(stubborn=True, lanyard=True))
    assert amounts(s.adjustments) == {"hazard_pay": 5}


def test_a_coupon_takes_three_gold_off_a_chosen_line() -> None:
    s = slip(busy(), Account(coupons=1), Choices(coupons=("repair",)))
    assert amounts(s.adjustments)["repair"] == 3 and s.account.coupons == 0


def test_a_coupon_cannot_push_a_line_below_zero() -> None:
    s = slip(ledger(clock_ins=2), Account(coupons=1), Choices(coupons=("timecard",)))
    assert amounts(s.adjustments) == {"timecard": 0}


def test_a_coupon_comes_after_every_waiver() -> None:
    account = Account(repair_plan=True, coupons=1)
    s = slip(ledger(repair=Repair("Vest", 8, 3)), account, Choices(coupons=("repair",)))
    assert amounts(s.adjustments) == {"repair": 0}  # 6 -> 3 (plan) -> 0 (coupon)


def test_unused_coupons_are_kept_for_the_next_slip() -> None:
    assert slip(busy(), Account(coupons=2)).account.coupons == 2
    s = slip(busy(), Account(coupons=2), Choices(coupons=("repair",)))
    assert s.account.coupons == 1


def test_a_coupon_cannot_forgive_the_old_balance_but_can_cut_the_late_fee() -> None:
    account = Account(debt=20, coupons=1)
    with pytest.raises(ValueError, match="no such line"):
        slip(ledger(), account, Choices(coupons=("carried",)))
    s = slip(ledger(), account, Choices(coupons=("late_fee",)))
    assert amounts(s.adjustments) == {"carried": 20, "late_fee": 0}


def test_a_coupon_needs_a_real_line_and_one_held() -> None:
    with pytest.raises(ValueError, match="no such line"):
        slip(busy(), Account(coupons=1), Choices(coupons=("mystery",)))
    with pytest.raises(ValueError, match="coupons"):
        slip(busy(), Account(coupons=1), Choices(coupons=("repair", "timecard")))


# -- the wallet and debt -----------------------------------------------------------------------


def test_a_positive_net_goes_to_the_wallet() -> None:
    s = slip(ledger(), Account(wallet=4))
    assert (s.wallet_after, s.debt_after) == (19, 0)


def test_a_zero_net_changes_nothing() -> None:
    s = slip(ledger(used=[Use(*KIT, 5, 3)]), Account(wallet=4))  # 15 - 15
    assert s.net == 0 and (s.wallet_after, s.debt_after) == (4, 0)


@pytest.mark.parametrize(
    ("wallet", "wallet_after", "debt_after"),
    [(0, 0, 5), (3, 0, 2), (5, 0, 0), (9, 4, 0)],
)
def test_a_shortfall_drains_the_wallet_then_becomes_debt(
    wallet: int, wallet_after: int, debt_after: int
) -> None:
    s = slip(ledger(used=[Use(*KIT, 5, 4)]), Account(wallet=wallet))  # net -5
    assert s.net == -5 and (s.wallet_after, s.debt_after) == (wallet_after, debt_after)


def test_a_positive_net_clears_all_earlier_debt() -> None:
    s = slip(ledger(), Account(wallet=0, debt=3))  # 15 - 3 - 1
    assert (s.net, s.wallet_after, s.debt_after) == (11, 11, 0)


@pytest.mark.parametrize(("debt", "fee"), [(1, 1), (9, 1), (10, 1), (11, 2), (20, 2), (21, 3)])
def test_the_late_fee_is_ten_percent_rounded_up(debt: int, fee: int) -> None:
    assert amounts(slip(ledger(), Account(debt=debt)).adjustments)["late_fee"] == fee


def test_no_debt_means_no_carried_or_late_lines() -> None:
    assert amounts(slip(ledger()).adjustments) == {}


def test_an_account_in_debt_is_on_hold() -> None:
    assert Account(debt=1).on_hold and not Account(debt=0, wallet=0).on_hold


# -- death -------------------------------------------------------------------------------------


def test_the_posthumous_slip_has_no_base_fee_and_adds_the_uniform_recovery_fee() -> None:
    led = ledger(died=True, salvage=salvage((*GEM, 1)), repair=Repair("Vest", 4, 1))
    s = slip(led, Account(wallet=3))
    assert [line.key for line in s.gross_lines] == ["salvage:rough_gem"]
    assert amounts(s.adjustments) == {"repair": 1, "uniform": 5}
    assert s.posthumous and s.net == -2 and (s.wallet_after, s.debt_after) == (1, 0)


def test_the_posthumous_slip_still_pays_a_premium_and_a_bounty_earned() -> None:
    s = slip(ledger(died=True, graveyard=True, bounty=True))
    assert s.gross == 5 + 6 and amounts(s.adjustments) == {"uniform": 5}


# -- score and titles --------------------------------------------------------------------------


def test_score_is_wealth_plus_levels_and_bounties() -> None:
    assert score(Account(wallet=20, debt=5), levels_cleared=3, bounties=2, params=E) == 15 + 30 + 10
    assert score(Account(wallet=0, debt=7), levels_cleared=0, bounties=0, params=E) == -7


@pytest.mark.parametrize(
    ("points", "key"),
    [(-50, "terminated"), (0, "terminated"), (1, "probationary"), (29, "probationary"),
     (30, "valued"), (59, "valued"), (60, "senior"), (99, "senior"), (100, "employee"),
     (500, "employee")],
)  # fmt: skip
def test_final_titles_follow_gdd_8_8(points: int, key: str) -> None:
    assert title_key(points, E) == key


# -- invariants over random ledgers ------------------------------------------------------------


def random_ledger(rng: Rng) -> Ledger:
    return Ledger(
        level=1 + rng.below(5),
        graveyard=rng.chance(1, 2),
        died=rng.chance(1, 4),
        bounty=rng.chance(1, 3),
        salvage=salvage(
            *[(f"v{i}", f"V{i}", 1 + rng.below(9), 1 + rng.below(3)) for i in range(rng.below(4))]
        ),
        used=[Use("kit", "Kit", rng.below(7), 1 + rng.below(3)) for _ in range(rng.below(4))],
        traps=rng.below(5),
        tripwires=rng.below(3),
        torches_dropped=rng.below(3),
        clock_ins=rng.below(9),
        stubborn=rng.chance(1, 2),
        repair=Repair("Armor", rng.below(25), 1 + rng.below(4)) if rng.chance(2, 3) else None,
        lanyard=rng.chance(1, 2),
        supply=[("Supply", rng.below(40))] if rng.chance(1, 4) else [],
    )


def random_account(rng: Rng) -> Account:
    return Account(
        wallet=rng.below(60), debt=rng.below(40), repair_plan=rng.chance(1, 2),
        hazard_waiver=rng.chance(1, 2), damage_waiver=rng.chance(1, 2), coupons=rng.below(3),
    )  # fmt: skip


def test_invariants_hold_over_thousands_of_random_slips() -> None:
    rng = Rng(2024)
    for _ in range(3000):
        led, account = random_ledger(rng), random_account(rng)
        repair = rng.chance(3, 4)
        first = slip(led, account, Choices(repair=repair))
        keys = [line.key for line in first.adjustments if line.key != "carried"]
        picks = tuple(rng.pick(keys) for _ in range(min(account.coupons, len(keys))))
        s = slip(led, account, Choices(repair=repair, coupons=picks))
        assert s.net == s.gross - s.adjusted
        assert s.wallet_after >= 0 and s.debt_after >= 0
        assert all(line.owed >= 0 for line in (*s.gross_lines, *s.adjustments))
        others = sum(line.owed for line in s.adjustments if line.key not in ("carried", "late_fee"))
        late = sum(line.owed for line in s.adjustments if line.key == "late_fee")
        before = account.wallet - account.debt
        after = s.wallet_after - s.debt_after
        assert after == before + s.gross - others - late  # wealth conservation, both branches
        assert s.account.coupons == account.coupons - len(picks)
