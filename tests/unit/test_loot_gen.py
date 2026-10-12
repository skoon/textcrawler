"""The `loot` stage (GDD 8.3, 8.4, 10.4 step 10): what lies on the floor and what dies with a
monster, rolled from the seed alone."""

import pytest

from minetoofar.content.balance import LEVELS
from minetoofar.content.docs import load_docs
from minetoofar.content.gamedata import found_charge
from minetoofar.content.loot import DOCUMENTS, load_loot
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.seed import Seed
from minetoofar.gen.loot import Loot
from minetoofar.gen.world import World, generate_world
from tests.helpers import DATA

SEEDS = [f"GOLD{n:04d}" for n in range(1, 25)]
LOOT = load_loot()
_SOURCES = {
    "weapon": "weapons",
    "armor": "armor",
    "shield": "shields",
    "hat": "hats",
    "trinket": "trinkets",
}


def worlds() -> list[World]:
    return [generate_world(Seed.parse(s), level) for s in SEEDS for level in range(1, LEVELS + 1)]


@pytest.fixture(scope="module")
def sample() -> list[World]:
    return worlds()


def test_loot_is_a_pure_function_of_seed_and_level() -> None:
    a = generate_world(Seed.parse("GOLD0001"), 3).loot
    b = generate_world(Seed.parse("GOLD0001"), 3).loot
    c = generate_world(Seed.parse("GOLD0002"), 3).loot
    assert a == b and a.dump() == b.dump() and a.sha256 == b.sha256
    assert a.sha256 != c.sha256


def test_the_dump_is_canonical_text() -> None:
    dump = generate_world(Seed.parse("GOLD0001"), 2).loot.dump()
    lines = dump.splitlines()
    assert lines[:3] == ["AMTF-LOOT", "seed GOLD0001", "level 2"]
    assert any(line.startswith("item ") for line in lines)
    assert dump.endswith("\n") and dump.isascii()


def test_the_number_of_items_follows_gdd_8_4(sample: list[World]) -> None:
    for w in sample:
        level = w.spec.level
        vaults = w.room_kinds.count("mausoleum")
        wanted = LOOT.base_items + LOOT.per_level_items * level + LOOT.extra_per_vault * vaults
        assert len(w.loot.items) == wanted + LOOT.lair_documents, (w.spec.seed, level)


def test_items_lie_on_plain_floor_apart_from_everything_else(sample: list[World]) -> None:
    for w in sample:
        grid = Grid(w.spec.width, w.spec.height, w.spec.tiles)
        rooms = {r.id: r for r in w.spec.rooms}
        entry = next(r.id for r in rooms.values() if r.x <= w.spec.entry.x < r.x + r.w
                     and r.y <= w.spec.entry.y < r.y + r.h)  # fmt: skip
        exit_ = next(r.id for r in rooms.values() if r.x <= w.spec.exit.x < r.x + r.w
                     and r.y <= w.spec.exit.y < r.y + r.h)  # fmt: skip
        taken = {m.pos for m in w.monsters.spawns} | {t for t, _ in w.traps.traps}
        seen = set()
        for pos, _ in w.loot.items:
            assert grid.get(pos.x, pos.y) in (Tile.FLOOR, Tile.CAVE_FLOOR), pos
            assert pos not in taken and pos not in seen and pos not in (w.spec.entry, w.spec.exit)
            seen.add(pos)
            room = next(r for r in rooms.values() if r.x <= pos.x < r.x + r.w
                        and r.y <= pos.y < r.y + r.h)  # fmt: skip
            assert room.id not in (entry, exit_), "loot in the entry or exit room"


def test_documents_are_capped_and_the_lair_always_holds_one(sample: list[World]) -> None:
    for w in sample:
        docs = [(p, i) for p, i in w.loot.items if i.id in DOCUMENTS]
        assert len(docs) <= LOOT.document_cap + LOOT.lair_documents
        lair = w.spec.rooms[w.humans.room_id]
        in_lair = [
            1
            for p, _ in docs
            if lair.x <= p.x < lair.x + lair.w and lair.y <= p.y < lair.y + lair.h  # fmt: skip
        ]
        assert len(in_lair) >= LOOT.lair_documents, (w.spec.seed, w.spec.level)


def test_document_texts_exist(sample: list[World]) -> None:
    book = load_docs()
    for w in sample:
        for _, i in w.loot.items + tuple((None, d) for _, d in w.loot.drops):  # type: ignore[operator]
            if i.id in DOCUMENTS:
                assert 0 <= i.text < len(book.texts[i.id])


def test_found_gear_matches_the_tier_for_its_level(sample: list[World]) -> None:
    items = DATA.items
    for w in sample:
        level = w.spec.level
        for _, i in w.loot.items:
            cat = items.category(i.id) if i.id not in DOCUMENTS else "document"
            if cat in ("weapon", "armor", "shield", "hat", "trinket"):
                tier = getattr(items, _SOURCES[cat])[i.id].tier
                assert tier <= (1 if level <= 2 else 2 if level <= 4 else 3), (i.id, level)
                if level == 5 and cat == "weapon":
                    assert tier >= 2


def test_found_armor_has_a_rolled_condition(sample: list[World]) -> None:
    armor = [i for w in sample for _, i in w.loot.items if i.id in DATA.items.armor]
    assert len(armor) > 30
    for i in armor:
        top = DATA.items.armor[i.id].dur
        assert top * LOOT.condition_min_pct // 100 <= i.dur <= top


def test_found_stock_bills_half_price_and_equipment_is_one_each(sample: list[World]) -> None:
    for w in sample:
        for _, i in w.loot.items:
            if i.id in DATA.items.consumables:
                assert (i.qty, i.charge) == (1, found_charge(DATA.items.consumables[i.id]))
            elif i.id not in DATA.items.valuables:
                assert i.qty == 1 and i.charge == 0


def test_the_mix_of_categories_is_in_the_neighbourhood_of_the_weights(sample: list[World]) -> None:
    kinds = [
        DATA.items.category(i.id) if i.id not in DOCUMENTS else "document"
        for w in sample
        for _, i in w.loot.items  # fmt: skip
    ]
    total = len(kinds)
    consumable = kinds.count("consumable") * 100 // total
    valuable = kinds.count("valuable") * 100 // total
    assert 30 <= consumable <= 50 and 15 <= valuable <= 35


def test_badgers_leave_gems_and_humans_leave_a_find(sample: list[World]) -> None:
    for w in sample:
        by_id = {i + 1: s for i, s in enumerate(w.monsters.spawns)}
        assert {mid for mid, _ in w.loot.drops} == {
            mid for mid, s in by_id.items() if s.kind in LOOT.drops
        }
        for mid, item in w.loot.drops:
            kind = by_id[mid].kind
            if kind == "gem_badger":
                assert item.id == "rough_gem" and 1 <= item.qty <= 2
            else:
                assert item.id in DATA.items.valuables or item.id in DOCUMENTS


def test_the_rogue_human_is_always_monster_number_one(sample: list[World]) -> None:
    assert all(w.monsters.spawns[0].kind in ("foreman_grimsby", "prospector_vane") for w in sample)
    assert all(any(mid == 1 for mid, _ in w.loot.drops) for w in sample)


def test_the_dump_hashes_what_it_lists() -> None:
    loot = generate_world(Seed.parse("GOLD0003"), 4).loot
    assert isinstance(loot, Loot) and len(loot.sha256) == 64
