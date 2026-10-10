from dataclasses import replace

import pytest

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.speech import load_speech
from minetoofar.core.geometry import DIRS8
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.pathing import distance_map
from minetoofar.core.seed import Seed
from minetoofar.gen.features import Features, apply_features, generate_features
from minetoofar.gen.humans import LAIRS, Humans, generate_humans
from minetoofar.gen.layout import generate_level
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.gen.rooms import room_containing
from minetoofar.gen.theme import HUMANS, Theme, generate_theme

P = load_balance().humans
SEEDS = ["BRASSLAMP42", "GOLD0001", "GOLD0042", "GOLD0092", "GOLD0100"]


def build(
    seed: str, level: int, human: str | None = None
) -> tuple[LevelSpec, Features, Theme, Humans]:
    parsed = Seed.parse(seed)
    spec = generate_level(parsed, level)
    theme = generate_theme(parsed, level)
    if human is not None:
        theme = replace(theme, human=human)
    features = generate_features(parsed, level, spec, theme)
    world = apply_features(spec, features)
    return world, features, theme, generate_humans(parsed, level, world, features, theme)


@pytest.mark.parametrize("seed", SEEDS)
def test_humans_are_deterministic(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        assert build(seed, level)[3] == build(seed, level)[3]


@pytest.mark.parametrize("seed", SEEDS)
def test_the_human_is_the_one_the_theme_rolled_in_the_matching_lair(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        for human in HUMANS:
            _, _, _, h = build(seed, level, human)
            assert h.kind == human and h.room_kind == LAIRS[human]


@pytest.mark.parametrize("seed", SEEDS)
def test_the_lair_is_an_ordinary_reachable_room_far_enough_along(seed: str) -> None:
    for level in range(1, LEVELS + 1):
        world, features, _, h = build(seed, level)
        grid = Grid(world.width, world.height, world.tiles)
        entry, exit_ = (
            room_containing(world.rooms, world.entry),
            room_containing(world.rooms, world.exit),
        )
        assert entry and exit_ and h.room_id not in (entry.id, exit_.id)
        assert features.room_kinds[h.room_id] not in ("flooded", "mausoleum")
        assert room_containing([world.rooms[h.room_id]], h.pos)
        assert grid.get(h.pos.x, h.pos.y) in (Tile.FLOOR, Tile.CAVE_FLOOR)
        dist = distance_map(grid, world.entry)
        assert h.pos in dist
        pct = P.last_level_distance_pct if level == LEVELS else P.distance_pct
        farthest = max(
            dist[p]
            for r in world.rooms
            if r.id not in (entry.id, exit_.id)
            for p in [h.pos]
            if room_containing([r], p)
        )
        assert dist[h.pos] * 100 >= pct * dist[world.exit] or dist[h.pos] == farthest


def test_the_last_level_stations_the_human_further_along() -> None:
    near = far = 0
    for i in range(1, 40):
        w4, _, _, h4 = build(f"GOLD{i:04d}", 4)
        w5, _, _, h5 = build(f"GOLD{i:04d}", 5)
        d4 = distance_map(Grid(w4.width, w4.height, w4.tiles), w4.entry)
        d5 = distance_map(Grid(w5.width, w5.height, w5.tiles), w5.entry)
        near += d4[h4.pos] * 100 // d4[w4.exit]
        far += d5[h5.pos] * 100 // d5[w5.exit]
    assert far > near


@pytest.mark.parametrize("human", HUMANS)
def test_speech_is_rolled_now_one_line_per_event(human: str) -> None:
    _, _, theme, h = build("BRASSLAMP42", 2, human)
    events = [e for e, _ in h.speech]
    assert events == [e for e in load_speech().events[human]]
    assert ("on_flee" in events) == (human == "prospector_vane")
    assert h.mood == theme.mood and all(text for _, text in h.speech)


def test_the_human_starts_idle_and_faces_one_of_the_eight_directions() -> None:
    spawn = build("BRASSLAMP42", 2)[3].spawn()
    assert spawn.state == "idle" and spawn.facing in DIRS8
    assert spawn.kind in HUMANS and dict(spawn.speech)["on_sight"]


def test_the_dump_is_canonical_text() -> None:
    _, _, _, h = build("BRASSLAMP42", 3, "prospector_vane")
    lines = h.dump().splitlines()
    assert lines[:3] == ["AMTF-HUMANS", "seed BRASSLAMP42", "level 3"]
    assert lines[3:5] == ["human prospector_vane", f"room {h.room_id} prospector_camp"]
    assert lines[5] == f"pos {h.pos.x} {h.pos.y}"
    assert any(line.startswith("line on_flee ") for line in lines)
    assert h.dump().isascii() and h.dump().endswith("\n") and len(h.sha256) == 64
