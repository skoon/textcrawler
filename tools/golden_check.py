"""Print `seed:level:stage:sha` for every golden seed so two machines can be diffed:
    uv run python tools/golden_check.py > a.txt     (native Windows)
    uv run python tools/golden_check.py > b.txt     (WSL)        then: diff a.txt b.txt
With --exe PATH the hashes come from the frozen EXE's `--hash` instead of the source tree.
"""

import argparse
import json
import subprocess
from pathlib import Path

from minetoofar.core.seed import Seed
from minetoofar.gen.world import generate_world

MANIFEST = Path(__file__).resolve().parents[1] / "tests" / "golden" / "manifest.json"


def source_hash(seed_text: str, level: int, stage: str) -> str:
    return generate_world(Seed.parse(seed_text), level).stage(stage).sha256


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", help="path to minetoofar.exe; verify against the manifest")
    parser.add_argument("--seeds", type=int, help="only check the first N manifest seeds")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    bad = 0
    for seed, levels in list(manifest["seeds"].items())[: args.seeds]:
        for level, stages in levels.items():
            for stage, want in stages.items():
                if args.exe:
                    run = subprocess.run(
                        [args.exe, "--seed", seed, "--level", level, "--stage", stage, "--hash"],
                        capture_output=True, text=True, check=True,
                    )  # fmt: skip
                    sha = run.stdout.strip()
                    bad += sha != want
                else:
                    sha = source_hash(seed, int(level), stage)
                print(f"{seed}:{level}:{stage}:{sha}")
    if args.exe:
        print(f"{'MISMATCH' if bad else 'OK'}: {bad} hash(es) differ from the manifest")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
