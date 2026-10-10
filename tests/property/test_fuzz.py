"""Large-sample generator fuzz. Run with: uv run pytest -m slow tests/property  (FUZZ_SEEDS=n)."""

import os

import pytest

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.seed import Seed
from minetoofar.gen.world import generate_world
from tests.layout_checks import check_level, check_world

COUNT = int(os.environ.get("FUZZ_SEEDS", "1000"))


@pytest.mark.slow
def test_thousand_seeds_generate_valid_worlds() -> None:
    balance, data = load_balance(), load_gamedata()
    for i in range(COUNT):
        seed = Seed.parse(f"FUZZ{i:05d}")
        for level in range(1, LEVELS + 1):
            try:
                world = generate_world(seed, level, balance, data)
                check_level(world.layout, balance)
                check_world(world, balance, data)
            except Exception as err:  # name the failing seed so it can be reproduced
                raise AssertionError(f"seed FUZZ{i:05d} level {level}: {err!r}") from err
