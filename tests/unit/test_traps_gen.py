from dataclasses import replace

import pytest

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.geometry import DIRS8, Pos
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.seed import Seed
from minetoofar.gen.features import apply_features, generate_features
from minetoofar.gen.humans import generate_humans
from minetoofar.gen.layout import generate_level
from minetoofar.gen.rooms import room_containing
from minetoofar.gen.theme import generate_theme
from minetoofar.gen.traps import Traps, generate_traps

B = load_balance()
KINDS = list(load_gamedata().traps)
SEEDS = ["BRASSLAMP42", "GOLD0001", "GOLD0042", "GOLD0092", "GOLD0100"]


def build(seed: str, level: int, human: str | None = None):  # type: ignore[no-untyped-def]
    parsed = Seed.parse(seed)
    spec = generate_level(parsed, level)
    theme = generate_theme(parsed, level)
    if human is not None:
        theme = replace(theme, human=human)
    features = generate_features(parsed, level, spec, theme)
    world = apply_features(spec, features)
    humans = generate_humans(parsed, level, world, features, theme)
    return world, features, humans, generate_traps(parsed, level, world, features, humans)


def camp(traps: Traps, world, humans) -> list[tuple[Pos, str]]:  # type: ignore[no-untyped-def]
    room = world.rooms[humans.room_id]
    return [(p, k) for p, k in traps.traps if room_containing([room], p)]


@pytest.mark.parametrize("seed", SEEDS)
def test_traps_are_deterministic(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        assert build(seed, level)[3] == build(seed, level)[3]


@pytest.mark.parametrize("seed", SEEDS)
def test_each_level_has_its_gdd_count_plus_the_camps_pre_laid_traps(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        for human in ("foreman_grimsby", "prospector_vane"):
            world, _, humans, traps = build(seed, level, human)
            extra = B.humans.camp_traps if human == "prospector_vane" else 0
            assert len(traps.traps) == B.trap_counts[level - 1] + extra


@pytest.mark.parametrize("seed", SEEDS)
def test_traps_lie_on_plain_floor_apart_from_each_other_and_out_of_the_entry_room(
    seed: str,
) -> None:
    for level in range(1, LEVELS + 1):
        world, _, _, traps = build(seed, level)
        grid = Grid(world.width, world.height, world.tiles)
        entry = room_containing(world.rooms, world.entry)
        positions = [p for p, _ in traps.traps]
        assert len(set(positions)) == len(positions)
        for p, kind in traps.traps:
            assert grid.get(p.x, p.y) in (Tile.FLOOR, Tile.CAVE_FLOOR)
            assert kind in KINDS
            assert not (entry and room_containing([entry], p))
            assert not any(p.step(d) in positions for d in DIRS8), f"{p} touches another trap"


@pytest.mark.parametrize("seed", SEEDS)
def test_static_traps_sit_in_corridors_and_doorways(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        world, _, humans, traps = build(seed, level, "foreman_grimsby")
        grid = Grid(world.width, world.height, world.tiles)
        for p, _ in traps.traps:
            in_corridor = room_containing(world.rooms, p) is None
            by_a_door = any(
                grid.get(p.x + dx, p.y + dy) == Tile.DOOR
                for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
            )
            assert in_corridor or by_a_door, f"{p} is in neither"


@pytest.mark.parametrize("seed", SEEDS)
def test_the_prospectors_camp_comes_with_two_traps_inside_it(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        world, _, humans, traps = build(seed, level, "prospector_vane")
        grid = Grid(world.width, world.height, world.tiles)
        inside = camp(traps, world, humans)
        assert len(inside) >= B.humans.camp_traps
        assert all(
            grid.get(p.x, p.y) in (Tile.FLOOR, Tile.CAVE_FLOOR) and p != humans.pos
            for p, _ in inside
        )


def test_all_three_kinds_turn_up_and_none_dominates() -> None:
    counts = dict.fromkeys(KINDS, 0)
    for i in range(1, 60):
        for _, kind in build(f"GOLD{i:04d}", 3)[3].traps:
            counts[kind] += 1
    total = sum(counts.values())
    assert all(total * 20 // 100 <= n for n in counts.values()), counts


def test_the_dump_is_canonical_text() -> None:
    _, _, _, traps = build("BRASSLAMP42", 3, "foreman_grimsby")
    lines = traps.dump().splitlines()
    assert lines[:4] == ["AMTF-TRAPS", "seed BRASSLAMP42", "level 3", f"count {len(traps.traps)}"]
    p, kind = traps.traps[0]
    assert lines[4] == f"trap {p.x} {p.y} {kind}"
    assert traps.dump().isascii() and len(traps.sha256) == 64
