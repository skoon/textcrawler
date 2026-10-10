"""The spawns stage (GDD 9.4, 9.5): the threat budget, the roster, and where each monster starts."""

from dataclasses import replace

import pytest

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.geometry import DIRS8
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.seed import Seed
from minetoofar.gen.rooms import room_containing
from minetoofar.gen.spawns import threat_spent
from minetoofar.gen.theme import generate_theme
from minetoofar.gen.world import World, generate_world

B = load_balance()
DATA = load_gamedata()
SEEDS = ["BRASSLAMP42", "GOLD0001", "GOLD0042", "GOLD0100"]


def world(seed: str, level: int, graveyard: bool | None = None) -> World:
    parsed = Seed.parse(seed)
    theme = generate_theme(parsed, level)
    if graveyard is not None:
        theme = replace(theme, graveyard=graveyard)
    return generate_world(parsed, level, theme=theme)


def budget(level: int, graveyard: bool) -> int:
    base = B.spawns.budget_base + B.spawns.budget_per_level * level
    return base * B.spawns.graveyard_budget_pct // 100 if graveyard else base


def kinds(w: World) -> list[str]:
    return [s.kind for s in w.spawns.spawns]


@pytest.mark.parametrize("seed", SEEDS)
def test_the_budget_is_spent_down_to_less_than_the_cheapest_monster(seed: str) -> None:
    cheapest = min(m.threat for m in DATA.monsters.values() if m.weight > 0)
    for level in range(1, LEVELS + 1):
        for graveyard in (False, True):
            w = world(seed, level, graveyard)
            spent = threat_spent(w.spawns, DATA)
            assert spent <= budget(level, graveyard) and budget(level, graveyard) - spent < cheapest


def test_a_graveyard_floor_has_a_quarter_more_budget_rounded_down() -> None:
    assert budget(1, True) == 14 * 125 // 100 == 17
    assert budget(5, True) == 30 * 125 // 100 == 37


@pytest.mark.parametrize("seed", SEEDS)
def test_every_level_has_at_least_one_beast(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        for graveyard in (False, True):
            beasts = [
                k
                for k in kinds(world(seed, level, graveyard))
                if DATA.monsters[k].faction == "beast"
            ]
            assert beasts, f"level {level}"


def test_level_gating_keeps_skeletons_for_level_two_and_wraiths_for_level_three() -> None:
    seen: dict[int, set[str]] = {level: set() for level in range(1, LEVELS + 1)}
    for i in range(1, 80):
        for level in range(1, LEVELS + 1):
            seen[level] |= set(kinds(world(f"GOLD{i:04d}", level)))
    assert "gravedigger_skeleton" not in seen[1] and "timecard_wraith" not in seen[1]
    assert "timecard_wraith" not in seen[2] and "gravedigger_skeleton" in seen[2]
    assert "timecard_wraith" in seen[3]
    assert seen[1] <= {"shambling_miner", "cave_vermin", "blind_ore_eel", "gem_badger"}


def test_graveyards_are_full_of_undead_and_normal_floors_of_beasts() -> None:
    def undead_share(graveyard: bool) -> int:
        undead = total = 0
        for i in range(1, 60):
            for k in kinds(world(f"GOLD{i:04d}", 3, graveyard)):
                total += 1
                undead += DATA.monsters[k].faction == "undead"
        return undead * 100 // total

    assert undead_share(True) > undead_share(False) + 20


@pytest.mark.parametrize("seed", SEEDS)
def test_eels_start_submerged_in_the_brine_of_a_flooded_gallery_and_nowhere_else(seed: str) -> None:
    eels = 0
    for level in range(1, LEVELS + 1):
        w = world(seed, level)
        grid = Grid(w.spec.width, w.spec.height, w.spec.tiles)
        for s in w.spawns.spawns:
            on_brine = grid.get(s.pos.x, s.pos.y) == Tile.BRINE
            assert on_brine == (s.kind == "blind_ore_eel")
            if s.kind == "blind_ore_eel":
                eels += 1
                assert s.state == "submerged"
                room = room_containing(w.spec.rooms, s.pos)
                assert room and w.room_kinds[room.id] == "flooded"
    assert eels >= 0


def test_vermin_come_in_packs_of_three_to_five_in_one_room() -> None:
    packs = 0
    for i in range(1, 60):
        w = world(f"GOLD{i:04d}", 2)
        by_pack: dict[int, list] = {}  # type: ignore[type-arg]
        for s in w.spawns.spawns:
            if s.kind == "cave_vermin":
                assert s.pack > 0
                by_pack.setdefault(s.pack, []).append(s)
            else:
                assert s.pack == 0
        for members in by_pack.values():
            packs += 1
            assert B.spawns.pack_min <= len(members) <= B.spawns.pack_max
            assert len({room_containing(w.spec.rooms, m.pos).id for m in members}) == 1  # type: ignore[union-attr]
            assert len({m.state for m in members}) == 1  # they sleep and wake together
    assert packs > 10


@pytest.mark.parametrize("seed", SEEDS)
def test_buried_miners_lie_in_open_graves_of_a_graveyard_and_only_there(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        for graveyard in (False, True):
            w = world(seed, level, graveyard)
            grid = Grid(w.spec.width, w.spec.height, w.spec.tiles)
            for s in w.spawns.spawns:
                if s.state == "buried":
                    assert graveyard and s.kind == "shambling_miner"
                    assert grid.get(s.pos.x, s.pos.y) == Tile.OPEN_GRAVE
                else:
                    assert grid.get(s.pos.x, s.pos.y) != Tile.OPEN_GRAVE


def test_a_graveyard_miner_is_buried_about_half_the_time_when_a_grave_is_free() -> None:
    buried = miners = 0
    for i in range(1, 60):
        for s in world(f"GOLD{i:04d}", 2, True).spawns.spawns:
            if s.kind == "shambling_miner":
                miners += 1
                buried += s.state == "buried"
    assert miners > 50 and 20 <= buried * 100 // miners <= 70


def test_about_a_third_sleep_and_four_in_five_in_bunk_rooms() -> None:
    asleep = total = bunk_asleep = bunk_total = 0
    for i in range(1, 80):
        w = world(f"GOLD{i:04d}", 1, False)
        for s in w.spawns.spawns:
            if s.state not in ("asleep", "idle"):
                continue
            room = room_containing(w.spec.rooms, s.pos)
            assert room is not None
            if w.room_kinds[room.id] == "bunk":
                bunk_total += 1
                bunk_asleep += s.state == "asleep"
            else:
                total += 1
                asleep += s.state == "asleep"
    assert 25 <= asleep * 100 // total <= 45
    assert bunk_total > 10 and 60 <= bunk_asleep * 100 // bunk_total <= 95


@pytest.mark.parametrize("seed", SEEDS)
def test_monsters_stay_clear_of_the_entry_and_exit_rooms_and_keep_their_distance(seed: str) -> None:
    from minetoofar.core.pathing import distance_map

    for level in range(1, LEVELS + 1):
        w = world(seed, level)
        grid = Grid(w.spec.width, w.spec.height, w.spec.tiles)
        dist = distance_map(grid, w.spec.entry)
        entry, exit_ = (
            room_containing(w.spec.rooms, w.spec.entry),
            room_containing(w.spec.rooms, w.spec.exit),
        )
        for s in w.spawns.spawns:
            room = room_containing(w.spec.rooms, s.pos)
            assert room and room.id not in (entry.id, exit_.id)  # type: ignore[union-attr]
            assert dist[s.pos] >= B.spawns.min_entry_distance


@pytest.mark.parametrize("seed", SEEDS)
def test_no_two_actors_share_a_tile_and_no_room_is_over_its_cap(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        w = world(seed, level)
        everyone = [s.pos for s in w.spawns.spawns] + [w.humans.pos]
        assert len(set(everyone)) == len(everyone)
        per_room: dict[int, int] = {}
        for p in everyone:
            room = room_containing(w.spec.rooms, p)
            assert room is not None
            per_room[room.id] = per_room.get(room.id, 0) + 1
        assert max(per_room.values()) <= B.spawns.room_cap


def test_every_spawn_faces_one_of_the_eight_directions() -> None:
    seen = {s.facing for i in range(1, 30) for s in world(f"GOLD{i:04d}", 2).spawns.spawns}
    assert seen == set(DIRS8)


def test_spawns_depend_only_on_the_seed_the_level_and_the_stages_before() -> None:
    a, b = world("GOLD0007", 3), world("GOLD0007", 3)
    assert a.spawns == b.spawns and a.spawns.sha256 == b.spawns.sha256
    assert world("GOLD0007", 4).spawns.sha256 != a.spawns.sha256
    assert world("GOLD0008", 3).spawns.sha256 != a.spawns.sha256


def test_the_dump_is_canonical_text() -> None:
    w = world("BRASSLAMP42", 2)
    lines = w.spawns.dump().splitlines()
    assert lines[:4] == [
        "AMTF-SPAWNS",
        "seed BRASSLAMP42",
        "level 2",
        f"count {len(w.spawns.spawns)}",
    ]
    s = w.spawns.spawns[0]
    fx, fy = s.facing
    assert lines[4] == f"spawn 0 {s.kind} {s.pos.x} {s.pos.y} {s.state} {fx} {fy} {s.pack}"
    assert w.spawns.dump().isascii() and w.spawns.dump().endswith("\n")
