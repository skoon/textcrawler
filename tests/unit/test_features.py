from dataclasses import replace

import pytest

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.core.geometry import DIRS8, Pos
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.pathing import distance_map
from minetoofar.core.seed import Seed
from minetoofar.gen.features import Features, apply_features, generate_features
from minetoofar.gen.layout import generate_level
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.gen.rooms import floor_tiles, interior_tiles, room_containing
from minetoofar.gen.theme import Theme, generate_theme

P = load_balance().features
SEEDS = ["BRASSLAMP42", "GOLD0001", "GOLD0042", "GOLD0092", "GOLD0100"]
PROPS = (Tile.GRAVESTONE, Tile.MONUMENT, Tile.OPEN_GRAVE)


def build(
    seed: str, level: int, graveyard: bool | None = None
) -> tuple[LevelSpec, Features, Theme]:
    parsed = Seed.parse(seed)
    spec = generate_level(parsed, level)
    theme = generate_theme(parsed, level)
    if graveyard is not None:
        theme = replace(theme, graveyard=graveyard)
    return spec, generate_features(parsed, level, spec, theme), theme


def kinds_of(spec: LevelSpec, features: Features, kind: str) -> list[int]:
    return [r.id for r in spec.rooms if features.room_kinds[r.id] == kind]


def tiles_of(features: Features, tile: Tile) -> list[Pos]:
    return [p for p, t in features.tiles if t == tile]


@pytest.mark.parametrize("seed", SEEDS)
def test_features_are_deterministic_and_ignore_other_stages(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        a = build(seed, level)[1]
        b = build(seed, level)[1]
        assert a == b and a.sha256 == b.sha256


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_rooms_are_left_alone(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        spec, features, _ = build(seed, level)
        entry, exit_ = (
            room_containing(spec.rooms, spec.entry),
            room_containing(spec.rooms, spec.exit),
        )
        assert entry and exit_
        assert features.room_kinds[entry.id] == "entry" and features.room_kinds[exit_.id] == "exit"
        for r in (entry, exit_):
            assert not any(room_containing([r], p) for p, _ in features.tiles)


@pytest.mark.parametrize("seed", SEEDS)
def test_every_level_has_a_flooded_gallery_and_level_three_has_two_or_three(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        spec, features, _ = build(seed, level)
        flooded = kinds_of(spec, features, "flooded")
        if level == 3:
            assert P.level3_flooded_min <= len(flooded) <= P.level3_flooded_max
        else:
            assert len(flooded) == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_a_flooded_gallery_is_brine_inside_with_a_dry_shore(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        spec, features, _ = build(seed, level)
        grid = Grid(spec.width, spec.height, spec.tiles)
        brine = set(tiles_of(features, Tile.BRINE))
        for rid in kinds_of(spec, features, "flooded"):
            room = spec.rooms[rid]
            inside = {p for p in brine if room_containing([room], p)}
            assert inside == set(interior_tiles(grid, room))
            assert len(inside) * 100 >= P.flood_min_pct * len(floor_tiles(grid, room))
            assert len(inside) < len(floor_tiles(grid, room))  # a shore remains
        in_flooded = {
            p
            for p in brine
            if any(room_containing([spec.rooms[r]], p) for r in kinds_of(spec, features, "flooded"))
        }
        assert in_flooded == brine  # brine nowhere else


@pytest.mark.parametrize("seed", SEEDS)
def test_rubble_is_only_in_collapse_rooms_which_are_caves(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        spec, features, _ = build(seed, level)
        collapses = kinds_of(spec, features, "collapse")
        assert all(spec.rooms[r].cave for r in collapses)
        for p in tiles_of(features, Tile.RUBBLE):
            room = room_containing(spec.rooms, p)
            assert room is not None and room.id in collapses


def test_about_a_quarter_of_a_collapse_is_rubble() -> None:
    rubble = floor = 0
    for i in range(1, 40):
        spec, features, _ = build(f"GOLD{i:04d}", 5)
        grid = Grid(spec.width, spec.height, spec.tiles)
        for rid in kinds_of(spec, features, "collapse"):
            floor += len(floor_tiles(grid, spec.rooms[rid]))
            rubble += sum(
                1 for p in tiles_of(features, Tile.RUBBLE) if room_containing([spec.rooms[rid]], p)
            )
    assert floor > 200 and 18 <= rubble * 100 // floor <= 32


def test_a_normal_floor_has_no_cemetery_at_all() -> None:
    for seed in SEEDS:
        for level in range(1, LEVELS + 1):
            spec, features, _ = build(seed, level, graveyard=False)
            assert not kinds_of(spec, features, "cemetery") and not kinds_of(
                spec, features, "mausoleum"
            )
            assert not any(t in PROPS for _, t in features.tiles)


@pytest.mark.parametrize("seed", SEEDS)
def test_a_graveyard_has_exactly_one_mausoleum_with_its_tombs(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        spec, features, _ = build(seed, level, graveyard=True)
        (mausoleum,) = kinds_of(spec, features, "mausoleum")
        tombs = [p for p in tiles_of(features, Tile.MONUMENT)]
        assert len(tombs) == P.monuments
        assert all(room_containing([spec.rooms[mausoleum]], p) for p in tombs)


def test_about_half_the_other_rooms_of_a_graveyard_are_cemetery_plots() -> None:
    plots = others = 0
    for i in range(1, 40):
        spec, features, _ = build(f"GOLD{i:04d}", 2, graveyard=True)
        free = [
            r
            for r in spec.rooms
            if features.room_kinds[r.id] in ("gallery", "bunk", "collapse", "cemetery")
        ]
        others += len(free)
        plots += len(kinds_of(spec, features, "cemetery"))
    assert 38 <= plots * 100 // others <= 62


@pytest.mark.parametrize("seed", SEEDS)
def test_cemetery_props_stand_on_interior_tiles_and_never_touch(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        spec, features, _ = build(seed, level, graveyard=True)
        grid = Grid(spec.width, spec.height, spec.tiles)
        props = [(p, t) for p, t in features.tiles if t in PROPS]
        positions = {p for p, _ in props}
        for p, _tile in props:
            room = room_containing(spec.rooms, p)
            assert room is not None and p in interior_tiles(grid, room)
            assert not any(p.step(d) in positions for d in DIRS8), f"{p} touches another prop"
        for rid in kinds_of(spec, features, "cemetery"):
            inside = [t for p, t in props if room_containing([spec.rooms[rid]], p)]
            space = len(interior_tiles(grid, spec.rooms[rid]))
            if space >= 9:  # room for a stone and a grave two tiles apart
                assert Tile.GRAVESTONE in inside and Tile.OPEN_GRAVE in inside
            elif space:
                assert inside


@pytest.mark.parametrize("seed", SEEDS)
def test_nothing_the_features_add_cuts_the_level_in_two(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        for graveyard in (False, True):
            spec, features, _ = build(seed, level, graveyard)
            before = set(distance_map(Grid(spec.width, spec.height, spec.tiles), spec.entry))
            world = apply_features(spec, features)
            after = set(distance_map(Grid(world.width, world.height, world.tiles), spec.entry))
            blocked = {p for p, t in features.tiles if t in (Tile.GRAVESTONE, Tile.MONUMENT)}
            assert after == before - blocked


def test_features_only_replace_plain_floor() -> None:
    spec, features, _ = build("GOLD0001", 3, graveyard=True)
    grid = Grid(spec.width, spec.height, spec.tiles)
    for p, t in features.tiles:
        assert grid.get(p.x, p.y) in (Tile.FLOOR, Tile.CAVE_FLOOR)
        assert t in (Tile.BRINE, Tile.RUBBLE, Tile.GRAVESTONE, Tile.MONUMENT, Tile.OPEN_GRAVE)


def test_apply_features_changes_nothing_but_those_tiles() -> None:
    spec, features, _ = build("GOLD0001", 3, graveyard=True)
    world = apply_features(spec, features)
    changed = {
        Pos(i % spec.width, i // spec.width)
        for i in range(len(spec.tiles))
        if spec.tiles[i] != world.tiles[i]
    }
    assert changed == {p for p, _ in features.tiles}
    assert (world.entry, world.exit, world.rooms, world.seed) == (
        spec.entry,
        spec.exit,
        spec.rooms,
        spec.seed,
    )


def test_about_one_room_in_five_of_the_rest_is_a_bunk_room() -> None:
    bunks = rest = 0
    for i in range(1, 40):
        spec, features, _ = build(f"GOLD{i:04d}", 1, graveyard=False)
        rest += sum(1 for k in features.room_kinds if k in ("gallery", "bunk"))
        bunks += len(kinds_of(spec, features, "bunk"))
    assert 12 <= bunks * 100 // rest <= 28


def test_the_dump_is_canonical_text() -> None:
    spec, features, _ = build("BRASSLAMP42", 3)
    lines = features.dump().splitlines()
    assert lines[:3] == ["AMTF-FEATURES", "seed BRASSLAMP42", "level 3"]
    assert lines[3] == f"rooms {len(spec.rooms)}"
    assert lines[4] == f"room 0 {features.room_kinds[0]}"
    count_line = next(line for line in lines if line.startswith("tiles "))
    assert count_line == f"tiles {len(features.tiles)}"
    first = features.tiles[0]
    assert f"tile {first[0].x} {first[0].y}" in features.dump()
    assert features.dump().isascii() and features.dump().endswith("\n")


def test_level_three_floods_what_it_can_when_fewer_rooms_qualify_than_the_roll_asks_for() -> None:
    """FUZZ00694 level 3 has exactly two floodable rooms; the roll may ask for three."""
    from minetoofar.gen.world import generate_world

    world = generate_world(Seed.parse("FUZZ00694"), 3)
    assert world.features.room_kinds.count("flooded") == 2
