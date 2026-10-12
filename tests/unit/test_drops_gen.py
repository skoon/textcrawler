"""The `drops` stage (GDD 8.5, 10.4 step 11): when supply crates land and what is in them."""

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.loot import load_loot
from minetoofar.core.seed import Seed
from minetoofar.gen.drops import SupplyDrop, generate_drops
from minetoofar.gen.world import generate_world
from tests.helpers import DATA

S = load_balance().supply
SEEDS = [f"GOLD{n:04d}" for n in range(1, 81)]


def every_drop_list() -> list[tuple[int, tuple[SupplyDrop, ...]]]:
    return [
        (level, generate_drops(Seed.parse(s), level).drops)
        for s in SEEDS
        for level in range(1, LEVELS + 1)
    ]


def test_drops_are_a_pure_function_of_seed_and_level() -> None:
    a = generate_drops(Seed.parse("GOLD0001"), 3)
    assert a == generate_drops(Seed.parse("GOLD0001"), 3)
    assert a.sha256 == generate_drops(Seed.parse("GOLD0001"), 3).sha256
    assert a.sha256 != generate_drops(Seed.parse("GOLD0002"), 3).sha256


def test_a_level_rolls_none_one_or_two_at_the_gdd_weights() -> None:
    counts = [0, 0, 0]
    for _, drops in every_drop_list():
        counts[len(drops)] += 1
    total = sum(counts)
    assert counts[1] > counts[0] > 0 and counts[2] > 0
    assert 14 <= counts[0] * 100 // total <= 36 and 42 <= counts[1] * 100 // total <= 68
    assert 8 <= counts[2] * 100 // total <= 32


def test_trigger_turns_are_inside_the_window_and_the_second_comes_late_enough() -> None:
    for _, drops in every_drop_list():
        for d in drops:
            assert S.trigger_min <= d.trigger <= S.trigger_max
        if len(drops) == 2:
            assert drops[1].trigger - drops[0].trigger >= S.second_gap


def test_a_crate_holds_three_distinct_consumable_lines_of_one_or_two() -> None:
    for _, drops in every_drop_list():
        for d in drops:
            stock = [ln for ln in d.lines if ln.item in DATA.items.consumables]
            assert len(stock) == S.lines
            assert len({ln.item for ln in stock}) == S.lines
            assert all(1 <= ln.qty <= S.qty_max for ln in stock)


def test_about_a_quarter_of_crates_add_one_piece_of_equipment() -> None:
    crates = [d for _, drops in every_drop_list() for d in drops]
    gear = [d for d in crates if len(d.lines) == S.lines + 1]
    assert all(len(d.lines) in (S.lines, S.lines + 1) for d in crates)
    assert 14 <= len(gear) * 100 // len(crates) <= 38


_SOURCES = {
    "weapon": "weapons",
    "armor": "armor",
    "shield": "shields",
    "hat": "hats",
    "trinket": "trinkets",
}


def test_the_equipment_follows_the_tier_table_and_arrives_in_good_condition() -> None:
    tiers = load_loot().tiers
    for level, drops in every_drop_list():
        top = 3 if tiers[2][level - 1] else 2 if tiers[1][level - 1] else 1
        for d in drops:
            for ln in d.lines:
                if ln.item in DATA.items.consumables:
                    continue
                kind = DATA.items.category(ln.item)
                table = getattr(DATA.items, _SOURCES[kind])
                assert ln.qty == 1 and table[ln.item].tier <= top
                if kind == "armor":
                    assert ln.dur == DATA.items.armor[ln.item].dur  # new from the crate


def test_the_stage_is_in_the_world_with_a_canonical_dump() -> None:
    world = generate_world(Seed.parse("GOLD0001"), 2)
    lines = world.drops.dump().splitlines()
    assert lines[:4] == [
        "AMTF-DROPS",
        "seed GOLD0001",
        "level 2",
        f"count {len(world.drops.drops)}",
    ]
    assert world.stage("drops") is world.drops and world.drops.dump().isascii()
