from dataclasses import replace

import pytest

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.seed import Seed
from minetoofar.gen.layout import generate_level
from minetoofar.gen.theme import HUMANS, generate_theme
from minetoofar.gen.world import STAGES, generate_world
from tests.layout_checks import check_level, check_world

BALANCE, DATA = load_balance(), load_gamedata()
SEEDS = [f"GOLD{i:04d}" for i in (1, 7, 42, 92, 100)] + ["BRASSLAMP42"]


@pytest.mark.parametrize("seed", SEEDS)
def test_every_generated_world_satisfies_every_invariant(seed: str) -> None:
    parsed = Seed.parse(seed)
    for level in range(1, LEVELS + 1):
        for graveyard in (False, True):
            for human in HUMANS:
                theme = replace(generate_theme(parsed, level), graveyard=graveyard, human=human)
                world = generate_world(parsed, level, theme=theme)
                check_level(world.layout, BALANCE)
                check_world(world, BALANCE, DATA)


def test_the_layout_stage_is_the_plain_layout() -> None:
    parsed = Seed.parse("GOLD0001")
    assert generate_world(parsed, 3).layout == generate_level(parsed, 3)


def test_the_world_is_a_pure_function_of_seed_and_level() -> None:
    a, b = generate_world(Seed.parse("GOLD0001"), 2), generate_world(Seed.parse("GOLD0001"), 2)
    assert a == b


def test_every_stage_names_an_output_with_a_dump_and_a_hash() -> None:
    world = generate_world(Seed.parse("GOLD0001"), 2)
    assert STAGES == ("layout", "theme", "features", "humans", "traps", "spawns")
    for name in STAGES:
        out = world.stage(name)
        assert out.dump().isascii() and out.dump().endswith("\n") and len(out.sha256) == 64


def test_the_human_comes_first_in_the_monster_list_the_game_is_given() -> None:
    world = generate_world(Seed.parse("GOLD0001"), 2)
    assert world.monsters.spawns[0].kind in HUMANS
    assert world.monsters.spawns[1:] == world.spawns.spawns


def test_the_lair_kind_is_merged_into_the_room_kinds() -> None:
    world = generate_world(Seed.parse("GOLD0001"), 2)
    assert world.room_kinds[world.humans.room_id] in ("foreman_office", "prospector_camp")
    assert world.features.room_kinds[world.humans.room_id] != world.humans.room_kind
