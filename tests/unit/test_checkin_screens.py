"""The text of the check-in screens (GDD 5.3) and the supply invoice (GDD 8.5)."""

from minetoofar.content.balance import load_balance
from minetoofar.content.text import load_text
from minetoofar.core.seed import Seed
from minetoofar.gen.desk import Memo
from minetoofar.gen.drops import SupplyLine
from minetoofar.sim.checkin import Checkin, FieldReport
from minetoofar.sim.economy import Account
from minetoofar.sim.game import Game
from minetoofar.sim.supply import invoice
from minetoofar.ui.panels import desk_lines, invoice_lines, memo_lines, report_lines
from tests.helpers import DATA

TEXT = load_text()
P = load_balance().supply


def report(**fields: object) -> FieldReport:
    base = dict(  # noqa: C408
        level=2, undead=5, beasts=7, human="Foreman Grimsby", human_down=False, valuables=3,
        turns=612, hp=35, max_hp=35, issued=(("Patch-Up Kit", 2), ("Torch", 1)),
        promoted_to=0, unlocked="",
    )  # fmt: skip
    return FieldReport(**{**base, **fields})  # type: ignore[arg-type]


def test_the_field_report_matches_the_gdd_mock_up() -> None:
    out = report_lines(report(), TEXT, "Stamp Mill and Assay Floor", 5)
    text = "\n".join(out)
    assert out[0] == "CHECK-IN 2 OF 5  ·  FIELD REPORT"
    for want in (
        "Work Order 2: Stamp Mill and Assay Floor",
        "Persistent Personnel resolved",
        "Wildlife Interface Events resolved",
        "Unauthorized Personnel (Foreman Grimsby)",
        "AT LARGE",
        "Valuables turned in",
        "Turns on site",
        "Wellness Break: HP restored to 35/35. No charge.",
        "Standard Issue topped up: Patch-Up Kit x2, Torch x1.",
        "[Enter] Pay slip",
    ):
        assert want in text, want
    money = {line.split(" ··")[0].strip(): line.rsplit(" ", 1)[1] for line in out if " ··" in line}
    assert money["Persistent Personnel resolved"] == "5" and money["Turns on site"] == "612"
    assert money["Work Order 2: Stamp Mill and Assay Floor"] == "CLOSED"
    assert all(len(x) <= 60 for x in out)


def test_a_retrieved_human_and_a_stocked_pack_read_differently() -> None:
    text = "\n".join(report_lines(report(human_down=True, issued=()), TEXT, "x", 5))
    assert "RETRIEVED" in text and "AT LARGE" not in text
    assert TEXT.line("report_issue_none") in text


def test_a_promotion_and_the_ability_it_brings_are_announced() -> None:
    text = "\n".join(report_lines(report(promoted_to=3, unlocked="Cleave"), TEXT, "x", 5))
    assert "Rank 3 is now on file." in text and "Cleave unlocked." in text


def test_the_final_report_has_no_wellness_break_or_standard_issue() -> None:
    text = "\n".join(report_lines(report(level=5), TEXT, "x", 5, final=True))
    assert "Wellness Break" not in text and "Standard Issue" not in text
    assert "[Enter] Pay slip" in text


def test_a_memo_has_its_sender_subject_and_wrapped_body() -> None:
    memo = Memo(
        "Regional Facilities Optimization",
        "RE: Your Valued Feedback",
        ("Team!", "x " * 80, "Enjoy!"),
    )
    out = memo_lines(memo, TEXT)
    assert out[0] == "RE: Your Valued Feedback" and "Team!" in out and "Enjoy!" in out
    assert all(len(x) <= 56 for x in out)
    assert out[-1] == TEXT.line("memo_keys")


def desk(wallet: int = 100, debt: int = 0) -> Checkin:
    g = Game.new(Seed.parse("GOLD0012"), 1)
    g.account = Account(wallet=wallet, debt=debt)
    g.check_out()
    return Checkin(g)


def test_the_desk_lists_numbered_offers_with_prices() -> None:
    c = desk()
    out = desk_lines(c, TEXT)
    assert out[0].startswith("REQUISITIONS DESK") and "Account in good standing" in out[0]
    numbered = [x for x in out if x.startswith("[")]
    assert len(numbered) == 4
    for i, line in enumerate(numbered):
        offer = c.offer(i)
        assert line.startswith(f"[{i + 1}] {offer.name}") and line.endswith(f"{offer.price}g")
    assert TEXT.line("desk_repair_note") in out
    assert all(len(x) <= 64 for x in out)


def test_a_sold_slot_says_sold_and_the_wallet_shown_is_what_is_left() -> None:
    c = desk()
    c.buy(0)
    out = desk_lines(c, TEXT, message="Bought!")
    assert next(x for x in out if x.startswith("[1]")).endswith("SOLD")
    assert f"Wallet {c.account.wallet}g" in out[0] and "Bought!" in out


def test_an_account_in_debt_shows_the_desk_on_hold() -> None:
    out = desk_lines(desk(wallet=0, debt=50), TEXT)
    assert "Account on hold" in out[0]
    assert TEXT.line("desk_hold_note") in " ".join(out)


def test_the_invoice_screen_matches_the_gdd_example() -> None:
    lines = [SupplyLine("patch_up_kit", 2, 0), SupplyLine("overtime_fizz", 1, 0),
             SupplyLine("welders_jacket", 1, 16)]  # fmt: skip
    inv = invoice(lines, (0, 1, 2), True, DATA, P)
    out = invoice_lines(1, inv, 0, TEXT, P.handling_pct)
    assert out[0] == "SUPPLY DROP INVOICE #1 (Express Cavern Delivery)"
    assert out[1].startswith("> [x] 1 Patch-Up Kit x2 @ 5g") and out[1].endswith("10g")
    assert out[2].startswith("  [x] 2 Overtime Fizz x1 @ 7g")
    text = "\n".join(out)
    assert "Welder's Jacket (T2)" in text and "22g" in text
    totals = {
        "Subtotal": "39g",
        "Expedited Handling (20%, rounded up)": "8g",
        "Delivery fee (if anything taken)": "2g",
        "Billed on your next slip": "49g",
    }
    for want, amount in totals.items():
        row = next(x for x in out if want in x)
        assert row.endswith(amount), row
    assert out[-1] == TEXT.line("invoice_keys")
    assert all(len(x) <= 70 for x in out)


def test_untaken_lines_are_unchecked_and_cost_nothing_on_the_invoice() -> None:
    lines = [SupplyLine("patch_up_kit", 2, 0), SupplyLine("overtime_fizz", 1, 0)]
    out = invoice_lines(2, invoice(lines, (1,), True, DATA, P), 1, TEXT, P.handling_pct)
    assert out[1].startswith("  [ ] 1") and out[2].startswith("> [x] 2")
    assert next(x for x in out if "Subtotal" in x).endswith("7g")
