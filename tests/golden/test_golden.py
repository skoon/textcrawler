"""Generation must stay byte-identical across runs, Python versions, and platforms."""

import difflib
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from minetoofar.content.balance import LEVELS
from minetoofar.core.seed import GEN_VERSION, Seed
from minetoofar.gen.world import STAGES, generate_world

GOLDEN = Path(__file__).parent
MANIFEST = json.loads((GOLDEN / "manifest.json").read_text("utf-8"))
SEPARATOR = "=" * 20 + "\n"


def test_manifest_is_for_this_generator_version() -> None:
    assert MANIFEST["gen_version"] == GEN_VERSION, "bump goldens with tools/regen_golden.py"


def stage_outputs(seed_text: str, level: int) -> dict[str, str]:
    world = generate_world(Seed.parse(seed_text), level)
    return {name: world.stage(name).dump() for name in STAGES}


def test_every_manifest_hash_still_matches() -> None:
    mismatches = []
    for seed_text, levels in MANIFEST["seeds"].items():
        for level, stages in levels.items():
            outputs = stage_outputs(seed_text, int(level))
            assert set(stages) == set(outputs), "manifest stages differ from the generator's"
            for stage, text in outputs.items():
                if hashlib.sha256(text.encode("ascii")).hexdigest() != stages[stage]:
                    mismatches.append(f"{seed_text} level {level} stage {stage}")
    assert not mismatches, "golden drift in: " + ", ".join(mismatches)


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("seed_text", MANIFEST["full_dumps"])
def test_full_text_dumps_match_line_for_line(seed_text: str, stage: str) -> None:
    expected = (GOLDEN / stage / f"{seed_text}.txt").read_text("utf-8")
    actual = SEPARATOR.join(
        stage_outputs(seed_text, level)[stage] for level in range(1, LEVELS + 1)
    )
    diff = "".join(
        difflib.unified_diff(expected.splitlines(True), actual.splitlines(True), "golden", "now")
    )
    assert actual == expected, diff[:2000]


HASH_ARGS = ["-m", "minetoofar", "--hash", "--seed", "BRASSLAMP42", "--level"]
ENV_VARIANTS = [
    {"PYTHONHASHSEED": "0"},
    {"PYTHONHASHSEED": "1"},
    {"PYTHONHASHSEED": "random"},
    {"PYTHONUTF8": "0", "LC_ALL": "C", "LANG": "C"},
    {"TZ": "Asia/Tokyo", "LC_ALL": "C.UTF-8"},
]


@pytest.mark.parametrize("variant", ENV_VARIANTS, ids=lambda v: ",".join(v))
def test_fresh_process_gives_the_same_hash(variant: dict[str, str]) -> None:
    expected = generate_world(Seed.parse("BRASSLAMP42"), 5).layout.sha256
    env = {**os.environ, **variant}
    out = subprocess.run(
        [sys.executable, "-X", "dev", *HASH_ARGS, "5"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == expected


@pytest.mark.parametrize("stage", [s for s in STAGES if s != "layout"])
@pytest.mark.parametrize("variant", ENV_VARIANTS[:3], ids=lambda v: ",".join(v))
def test_fresh_process_gives_the_same_hash_for_every_later_stage(
    stage: str, variant: dict[str, str]
) -> None:
    expected = generate_world(Seed.parse("BRASSLAMP42"), 4).stage(stage).sha256
    out = subprocess.run(
        [sys.executable, "-X", "dev", *HASH_ARGS, "4", "--stage", stage],
        env={**os.environ, **variant}, capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert out.stdout.strip() == expected


def test_optimized_interpreter_gives_the_same_hash() -> None:
    expected = generate_world(Seed.parse("BRASSLAMP42"), 2).layout.sha256
    out = subprocess.run(
        [sys.executable, "-O", *HASH_ARGS, "2"], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == expected
