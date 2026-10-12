"""The Requisitions Desk catalog, the memo templates, and the supply-drop numbers."""

from importlib import resources

import pytest

from minetoofar.content.balance import load_balance
from minetoofar.content.desk import DeskError, load_desk, parse_desk
from minetoofar.content.memos import MemoError, load_memos, parse_memos
from tests.helpers import DATA


def shipped(name: str) -> str:
    return resources.files("minetoofar").joinpath("data", name).read_text("utf-8")


def test_shipped_supply_numbers_match_gdd_8_5() -> None:
    s = load_balance().supply
    assert (s.none_weight, s.one_weight, s.two_weight) == (25, 55, 20)
    assert (s.trigger_min, s.trigger_max, s.second_gap) == (120, 700, 250)
    assert (s.lines, s.qty_max, s.equipment_pct) == (3, 2, 25)
    assert (s.handling_pct, s.delivery_fee, s.landing_radius) == (20, 2, 3)
    assert (s.price_t1, s.price_t2, s.price_t3) == (12, 22, 34)
    assert load_balance().checkin.desk_slots == 4


def test_the_shipped_catalog_matches_the_gdd_prices() -> None:
    catalog = load_desk()
    assert {k: v.price for k, v in catalog.items()} == {
        "torch_bundle": 5, "kit_bundle": 8, "sharpening_service": 12, "hone_and_balance": 12,
        "armor_plating": 18, "reinforced_hard_hat": 10, "wellness_seminar": 10,
        "repair_plan": 6, "property_damage_waiver": 5, "hazard_waiver": 6,
    }  # fmt: skip
    assert catalog["torch_bundle"].item == "torch" and catalog["torch_bundle"].qty == 3
    assert catalog["kit_bundle"].item == "patch_up_kit" and catalog["kit_bundle"].qty == 2
    assert (catalog["sharpening_service"].value, catalog["sharpening_service"].cap) == (1, 3)
    assert (catalog["hone_and_balance"].value, catalog["hone_and_balance"].cap) == (1, 2)
    assert (catalog["armor_plating"].value, catalog["wellness_seminar"].value) == (4, 3)


def test_there_are_bundles_for_slot_one_and_enough_else_to_fill_the_rest() -> None:
    catalog = load_desk()
    bundles = [k for k, v in catalog.items() if v.effect == "bundle"]
    others = [k for k, v in catalog.items() if v.effect != "bundle" and v.weight > 0]
    assert len(bundles) >= 2 and len(others) >= load_balance().checkin.desk_slots - 1


@pytest.mark.parametrize(
    ("old", "new", "word"),
    [
        ("price = 5\n", "price = 5.5\n", "integer"),
        ('effect = "bundle"\nitem = "torch"', 'effect = "explode"\nitem = "torch"', "effect"),
        ('item = "torch"\nqty = 3', 'item = "nonesuch"\nqty = 3', "nonesuch"),
        ("weight = 50\neffect", "weight = -1\neffect", "negative"),
        ('blurb = "3 prepaid torches"\n', "", "missing"),
    ],
)
def test_bad_catalogs_are_rejected(old: str, new: str, word: str) -> None:
    with pytest.raises(DeskError, match=word):
        parse_desk(shipped("desk.toml").replace(old, new, 1), DATA)


def test_a_catalog_needs_two_bundles() -> None:
    text = shipped("desk.toml")
    head, _, rest = text.partition("[kit_bundle]")
    _, _, tail = rest.partition("[sharpening_service]")
    with pytest.raises(DeskError, match="bundle"):
        parse_desk(head + "[sharpening_service]" + tail, DATA)


# -- memos --------------------------------------------------------------------------------------


def test_the_shipped_memos_have_every_part() -> None:
    book = load_memos()
    assert len(book.senders) >= 4 and len(book.subjects) >= 4 and len(book.openers) >= 4
    assert len(book.policies) >= 5 and all(len(p) == 2 and p[0] != p[1] for p in book.policies)
    assert len(book.reminders) >= 4 and len(book.signoffs) >= 4
    assert "{level}" in book.graveyard_notice and "{premium}" in book.graveyard_notice
    assert "{level}" in book.plain_notice


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("senders = [", "senderz = ["),
        ('graveyard_notice = "Per', 'graveyard_notice = 3 # "Per'),
        ('plain_notice = "Level {level}', 'plain_notice = "Level {lvl}'),
    ],
)
def test_bad_memo_files_are_rejected(old: str, new: str) -> None:
    with pytest.raises(MemoError):
        parse_memos(shipped("text/memos.toml").replace(old, new, 1))


def test_a_policy_pair_must_be_two_different_lines() -> None:
    text = shipped("text/memos.toml")
    bad = text.replace(
        '"Hard Hats are now optional, and also mandatory."',
        '"Hard Hats are mandatory at all times."',
    )
    with pytest.raises(MemoError, match="pair"):
        parse_memos(bad)
