"""Rewrite tests/golden after an intentional generator change. Usage:
    uv run python tools/regen_golden.py --reason "why the output changed"
The generator is frozen (M9): a hash that is already in the manifest may not change unless
GEN_VERSION has been bumped first, because a bump breaks every shared seed. New seeds are fine.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from minetoofar.content.balance import LEVELS
from minetoofar.core.seed import GEN_VERSION, Seed
from minetoofar.gen.world import STAGES, generate_world

GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "golden"
SEEDS = [f"GOLD{i:04d}" for i in range(1, 101)]
FULL_DUMPS = SEEDS[:3]
SEPARATOR = "=" * 20 + "\n"
SHOWN = 10  # changed hashes named in the refusal


class FrozenGenerator(Exception):
    """The output of a released generator version would change."""


def changed_hashes(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Every "seed Llevel stage" whose hash is in both manifests and differs."""
    out = []
    for seed, levels in old["seeds"].items():
        for level, stages in levels.items():
            for stage, digest in stages.items():
                if new["seeds"].get(seed, {}).get(level, {}).get(stage, digest) != digest:
                    out.append(f"{seed} L{level} {stage}")
    return out


def check_freeze(old: dict[str, Any] | None, new: dict[str, Any]) -> None:
    """Refuse a regeneration that changes released output without a new GEN_VERSION."""
    if old is None or old["gen_version"] != new["gen_version"]:
        return
    changed = changed_hashes(old, new)
    if changed:
        more = f" and {len(changed) - SHOWN} more" if len(changed) > SHOWN else ""
        raise FrozenGenerator(
            f"generator version {new['gen_version']} is frozen, but {len(changed)} hashes would "
            f"change ({', '.join(changed[:SHOWN])}{more}). Bump GEN_VERSION in core/seed.py "
            "first: every shared seed will make a different mine."
        )


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
    path = GOLDEN / "manifest.json"
    try:
        check_freeze(json.loads(path.read_text("utf-8")) if path.exists() else None, manifest)
    except FrozenGenerator as refusal:
        raise SystemExit(f"refused: {refusal}") from refusal
    path.write_text(json.dumps(manifest, indent=1) + "\n", "utf-8", newline="\n")
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
