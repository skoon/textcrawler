"""Balance simulator (GDD 8.6 targets): the scripted bot plays whole runs, seeds in parallel.

    uv run python tools/balance_sim.py [--seeds 200] [--policy careful] [--classes fighter ...]

Prints, per class: outcomes, where deaths happen and what did them, net pay per cleared level,
how many winning runs end in debt, and the score spread; then checks each against the targets.
"""

import argparse
import statistics
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from minetoofar.core.seed import Seed
from minetoofar.sim.autoplay import RunLog, play_run
from minetoofar.sim.bot import CAREFUL, RECKLESS, Policy

POLICIES: dict[str, Policy] = {"careful": CAREFUL, "reckless": RECKLESS}
CLASSES = ("fighter", "rogue", "ranger")
NET_TARGET = (4, 10)  # median net pay per level, competent play
DEBT_LIMIT_PCT = 15  # of runs that reach the end
SCORE_TARGET = (60, 110)  # full-run score, competent play
FIELDS = ("gross", "adjusted", "net")


@dataclass(frozen=True)
class Verdict:
    label: str
    value: str
    ok: bool


def _one(job: tuple[str, str, str]) -> RunLog:
    seed, class_id, policy = job
    return play_run(Seed.parse(seed), class_id, POLICIES[policy])


def run_class(class_id: str, seeds: int, policy: str, pool: ProcessPoolExecutor) -> list[RunLog]:
    jobs = [(f"SIM{i:04d}", class_id, policy) for i in range(1, seeds + 1)]
    return list(pool.map(_one, jobs, chunksize=2))


def median(values: list[int]) -> float | None:
    return statistics.median(values) if values else None


def judge(runs: list[RunLog], policy: str = "careful") -> list[Verdict]:
    """Competent play must meet the three targets; sloppy play must lose money."""
    if policy == "reckless":
        every = median([lv.net for r in runs for lv in r.levels])
        return [Verdict("median net over every slip", f"{every}", every is not None and every < 0)]
    won = [r for r in runs if r.outcome == "victory"]
    nets = [lv.net for r in runs for lv in r.levels if lv.outcome == "cleared"]
    med = median(nets)
    in_debt = sum(1 for r in won if r.debt > 0)
    scores = median([r.score for r in won])
    return [
        Verdict(
            "median net per cleared level", f"{med}",
            med is not None and NET_TARGET[0] <= med <= NET_TARGET[1],
        ),
        Verdict(
            "winning runs ending in debt", f"{in_debt}/{len(won)}",
            bool(won) and in_debt * 100 < DEBT_LIMIT_PCT * len(won),
        ),
        Verdict(
            "median score of a full run", f"{scores}",
            scores is not None and SCORE_TARGET[0] <= scores <= SCORE_TARGET[1],
        ),
    ]  # fmt: skip


def report(class_id: str, runs: list[RunLog], policy: str) -> list[Verdict]:
    outcomes = Counter(r.outcome for r in runs)
    deaths = Counter(r.levels[-1].level for r in runs if r.outcome == "death")
    killers = Counter(r.levels[-1].cause for r in runs if r.outcome == "death")
    print(f"== {class_id}: {len(runs)} runs  {dict(outcomes)}")
    print(f"   deaths by level {dict(sorted(deaths.items()))}")
    print(f"   killers {killers.most_common(6)}")
    for level in range(1, 6):
        done = [
            lv for r in runs for lv in r.levels if lv.level == level and lv.outcome == "cleared"
        ]
        if done:
            gross, adjusted, net = (median([getattr(lv, f) for lv in done]) for f in FIELDS)
            print(
                f"   L{level}: cleared {len(done):3d}  gross {gross} adjusted {adjusted} net {net}"
            )
    verdicts = judge(runs, policy)
    for v in verdicts:
        print(f"   {'ok  ' if v.ok else 'MISS'} {v.label}: {v.value}")
    return verdicts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--policy", choices=sorted(POLICIES), default="careful")
    ap.add_argument("--classes", nargs="+", choices=CLASSES, default=list(CLASSES))
    args = ap.parse_args(argv)
    missed = 0
    with ProcessPoolExecutor() as pool:
        for class_id in args.classes:
            verdicts = report(
                class_id, run_class(class_id, args.seeds, args.policy, pool), args.policy
            )
            missed += sum(1 for v in verdicts if not v.ok)
    print("targets met" if not missed else f"{missed} target(s) missed")
    return 0 if not missed else 1


if __name__ == "__main__":
    sys.exit(main())
