"""Rewrite tests/golden after an intentional generator change. Usage:
    uv run python tools/regen_golden.py --reason "why the output changed"
Before the M9 freeze goldens may change freely; afterwards GEN_VERSION must be bumped first.
"""

import argparse
import hashlib
import json
from pathlib import Path

from minetoofar.content.balance import LEVELS
from minetoofar.core.seed import GEN_VERSION, Seed
from minetoofar.gen.world import STAGES, generate_world

GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "golden"
SEEDS = [f"GOLD{i:04d}" for i in range(1, 101)]
FULL_DUMPS = SEEDS[:3]
SEPARATOR = "=" * 20 + "\n"


def stage_texts(seed_text: str, level: int) -> dict[str, str]:
    world = generate_world(Seed.parse(seed_text), level)
    return {name: world.stage(name).dump() for name in STAGES}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reason", required=True, help="recorded in tests/golden/CHANGELOG.md")
    args = parser.parse_args()
    if not args.reason.strip():
        parser.error("--reason must not be empty")

    seeds = {
        s: {
            str(level): {
                stage: hashlib.sha256(text.encode("ascii")).hexdigest()
                for stage, text in stage_texts(s, level).items()
            }
            for level in range(1, LEVELS + 1)
        }
        for s in SEEDS
    }
    manifest = {"gen_version": GEN_VERSION, "full_dumps": FULL_DUMPS, "seeds": seeds}
    (GOLDEN / "manifest.json").write_text(
        json.dumps(manifest, indent=1) + "\n", "utf-8", newline="\n"
    )
    for stage in STAGES:
        (GOLDEN / stage).mkdir(exist_ok=True)
        for s in FULL_DUMPS:
            text = SEPARATOR.join(stage_texts(s, lv)[stage] for lv in range(1, LEVELS + 1))
            (GOLDEN / stage / f"{s}.txt").write_text(text, "utf-8", newline="\n")
    with (GOLDEN / "CHANGELOG.md").open("a", encoding="utf-8", newline="\n") as log:
        log.write(f"- gen_version {GEN_VERSION}: {args.reason.strip()}\n")
    print(f"wrote {len(SEEDS)} seeds x {LEVELS} levels x {len(STAGES)} stages")


if __name__ == "__main__":
    main()
