import dataclasses

import pytest

from minetoofar.content.balance import load_balance
from minetoofar.core.seed import Seed
from minetoofar.gen.layout import GenerationError, generate_level
from tests.layout_checks import check_level

BALANCE = load_balance()
SEEDS = [Seed.parse(f"UNIT{i:03d}") for i in range(30)]


def test_same_seed_and_level_give_identical_dump() -> None:
    seed = Seed.parse("BRASSLAMP42")
    a = generate_level(seed, 3, BALANCE).dump()
    b = generate_level(seed, 3, BALANCE).dump()
    assert a == b


def test_seed_and_level_change_the_dungeon() -> None:
    dumps = {
        generate_level(seed, level, BALANCE).dump() for seed in SEEDS[:3] for level in (1, 2, 3)
    }
    assert len(dumps) == 9


def test_level_out_of_range_is_rejected() -> None:
    with pytest.raises(ValueError):
        generate_level(SEEDS[0], 0, BALANCE)
    with pytest.raises(ValueError):
        generate_level(SEEDS[0], 6, BALANCE)


def test_levels_are_generated_independently() -> None:
    # Level 4 must not depend on having generated levels 1-3 first (GDD 10.1).
    cold = generate_level(SEEDS[1], 4, BALANCE).dump()
    for lvl in (1, 2, 3):
        generate_level(SEEDS[1], lvl, BALANCE)
    assert generate_level(SEEDS[1], 4, BALANCE).dump() == cold


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_structural_invariants_hold(level: int) -> None:
    for seed in SEEDS:
        check_level(generate_level(seed, level, BALANCE), BALANCE)


def test_level_one_has_no_cavern_rooms_and_level_five_has_some() -> None:
    l1 = [r.cave for s in SEEDS for r in generate_level(s, 1, BALANCE).rooms]
    l5 = [r.cave for s in SEEDS for r in generate_level(s, 5, BALANCE).rooms]
    assert not any(l1)
    assert sum(l5) > len(l5) // 2


def test_dump_is_canonical_ascii_text() -> None:
    spec = generate_level(Seed.parse("BRASSLAMP42"), 3, BALANCE)
    text = spec.dump()
    assert text.isascii() and text.endswith("\n") and "\r" not in text
    lines = text.split("\n")
    assert lines[0] == "AMTF-LEVEL"
    assert "level 3" in lines and "seed BRASSLAMP42" in lines
    assert lines.index("map") + 1 + BALANCE.layout.height == len(lines) - 1
    assert spec.sha256 == __import__("hashlib").sha256(text.encode("ascii")).hexdigest()


def test_unsatisfiable_balance_fails_loudly() -> None:
    impossible = dataclasses.replace(
        BALANCE, layout=dataclasses.replace(BALANCE.layout, rooms_min=99, max_attempts=3)
    )
    with pytest.raises(GenerationError, match="3 attempts"):
        generate_level(SEEDS[0], 1, impossible)
