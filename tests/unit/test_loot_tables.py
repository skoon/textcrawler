"""data/loot.toml and data/text/docs.toml: the tables that decide what lies on the floor."""

import pytest

from minetoofar.content.docs import DocError, load_docs, parse_docs
from minetoofar.content.loot import LootError, load_loot, parse_loot
from tests.helpers import DATA


def test_shipped_loot_numbers_match_gdd_8_3_and_8_4() -> None:
    t = load_loot()
    assert (t.base_items, t.per_level_items, t.extra_per_vault) == (7, 1, 2)  # 7 + L, +2
    assert (t.document_cap, t.condition_min_pct, t.lair_documents) == (2, 50, 1)
    assert dict(t.categories) == {"consumable": 40, "valuable": 25, "equipment": 20, "document": 15}
    assert dict(t.consumables) == {
        "patch_up_kit": 40, "torch": 30, "overtime_fizz": 15, "sanctified_detergent": 15,
    }  # fmt: skip
    assert dict(t.equipment) == {"weapon": 30, "armor": 25, "trinket": 20, "hat": 15, "shield": 10}
    assert dict(t.documents) == {"memo": 70, "coupon": 20, "map": 10}
    assert dict(t.rooms) == {
        "mausoleum": 6, "lair": 4, "collapse": 3, "gallery": 2, "bunk": 2, "flooded": 2,
        "cemetery": 2,
    }  # fmt: skip


def test_tiers_follow_gdd_8_4_and_sum_to_a_hundred() -> None:
    t = load_loot()
    assert t.tiers[0] == (100, 100, 70, 70, 0)  # T1 only on L1-2, 70% on L3-4
    assert t.tiers[1] == (0, 0, 30, 30, 70)
    assert t.tiers[2] == (0, 0, 0, 0, 30)  # T3 only on L5
    assert all(sum(col) == 100 for col in zip(*t.tiers, strict=True))


def test_drops_follow_gdd_7_6_and_9_6() -> None:
    drops = load_loot().drops
    assert (drops["gem_badger"].item, drops["gem_badger"].max) == ("rough_gem", 2)
    assert drops["foreman_grimsby"].item == "*" and drops["prospector_vane"].item == "*"


def shipped_text() -> str:
    from importlib import resources

    return resources.files("minetoofar").joinpath("data", "loot.toml").read_text("utf-8")


@pytest.mark.parametrize(
    ("old", "new", "word"),
    [
        ("torch = 30", "torch = 30.5", "integer"),
        ("torch = 30", "nonesuch = 30", "nonesuch"),
        ("tier1 = [100, 100, 70, 70, 0]", "tier1 = [100, 100, 70, 70, 10]", "sum"),
        ("tier3 = [0, 0, 0, 0, 30]", "tier3 = [0, 0, 30]", "five"),
        ('item = "rough_gem"', 'item = "nonesuch"', "nonesuch"),
        ("[drop.gem_badger]", "[drop.nonesuch]", "nonesuch"),
        ("mausoleum = 6", "mausoleum = -1", "negative"),
        ("memo = 70\ncoupon = 20\nmap = 10", "memo = 0\ncoupon = 0\nmap = 0", "weight"),
    ],
)
def test_bad_loot_tables_are_rejected(old: str, new: str, word: str) -> None:
    with pytest.raises(LootError, match=word):
        parse_loot(shipped_text().replace(old, new), DATA)


def test_missing_and_unknown_sections_are_rejected() -> None:
    with pytest.raises(LootError, match="missing"):
        parse_loot(shipped_text().replace("[tiers]", "[tierz]"), DATA)
    with pytest.raises(LootError, match="categories"):
        parse_loot(shipped_text().replace("valuable = 25\n", ""), DATA)


# -- documents ----------------------------------------------------------------------------------


def test_every_kind_of_document_has_several_texts() -> None:
    book = load_docs()
    assert len(book.texts["memo"]) >= 10 and len(book.texts["coupon"]) >= 3
    assert len(book.texts["map"]) >= 3
    assert all(t and len(t) <= 160 for texts in book.texts.values() for t in texts)


@pytest.mark.parametrize(
    "text",
    [
        'memo = ["a"]\ncoupon = ["b"]',
        'memo = []\ncoupon = ["b"]\nmap = ["c"]',
        'memo = [1]\ncoupon = ["b"]\nmap = ["c"]',
        'memo = ["a"]\ncoupon = ["b"]\nmap = ["c"]\nextra = ["d"]',
    ],
)
def test_bad_document_files_are_rejected(text: str) -> None:
    with pytest.raises(DocError):
        parse_docs(text)
