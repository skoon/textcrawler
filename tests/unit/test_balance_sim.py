"""The balance simulator's verdicts (GDD 8.6 targets), judged on made-up runs."""

import importlib.util
from pathlib import Path
from types import ModuleType

from minetoofar.sim.autoplay import LevelLog, RunLog

TOOL = Path(__file__).resolve().parents[2] / "tools" / "balance_sim.py"


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("balance_sim", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sim = load_tool()


def level(n: int, net: int, outcome: str = "cleared", debt: int = 0) -> LevelLog:
    return LevelLog(n, outcome, 20, 20 - net, net, 100, 0, debt)


def run(nets: list[int], outcome: str = "victory", score: int = 80, debt: int = 0) -> RunLog:
    levels = [level(i + 1, n) for i, n in enumerate(nets)]
    return RunLog("SIM0001", "fighter", outcome, levels, score, "Senior Associate", 0, debt)


def verdicts(runs: list[RunLog], policy: str = "careful") -> dict[str, bool]:
    return {v.label: v.ok for v in sim.judge(runs, policy)}


def test_competent_play_inside_every_target_passes() -> None:
    runs = [run([6, 7, 8, 7, 6]) for _ in range(10)]
    assert all(verdicts(runs).values())


def test_median_net_outside_four_to_ten_is_a_miss() -> None:
    assert not verdicts([run([15, 15, 15, 15, 15])])["median net per cleared level"]
    assert not verdicts([run([1, 2, 3, 2, 1])])["median net per cleared level"]
    assert verdicts([run([4, 4, 4, 4, 4])])["median net per cleared level"]
    assert verdicts([run([10, 10, 10, 10, 10])])["median net per cleared level"]


def test_net_counts_only_levels_that_were_cleared() -> None:
    died = RunLog("S", "fighter", "death", [level(1, 6), level(2, -30, "died")], 0, "x", 0, 30)
    assert verdicts([died])["median net per cleared level"]


def test_fifteen_percent_of_winners_in_debt_is_a_miss() -> None:
    fine = [run([6] * 5) for _ in range(18)] + [run([6] * 5, debt=3) for _ in range(2)]
    over = [run([6] * 5) for _ in range(17)] + [run([6] * 5, debt=3) for _ in range(3)]
    assert verdicts(fine)["winning runs ending in debt"]
    assert not verdicts(over)["winning runs ending in debt"]


def test_score_outside_sixty_to_one_ten_is_a_miss() -> None:
    assert not verdicts([run([6] * 5, score=59)])["median score of a full run"]
    assert verdicts([run([6] * 5, score=60)])["median score of a full run"]
    assert verdicts([run([6] * 5, score=110)])["median score of a full run"]
    assert not verdicts([run([6] * 5, score=111)])["median score of a full run"]


def test_no_winners_means_the_score_and_debt_targets_are_missed_not_skipped() -> None:
    dead = RunLog("S", "fighter", "death", [level(1, 6), level(2, -9, "died")], 0, "x", 0, 9)
    got = verdicts([dead])
    assert not got["winning runs ending in debt"] and not got["median score of a full run"]


def test_sloppy_play_must_lose_money_across_every_slip_it_signs() -> None:
    ruined = RunLog("S", "fighter", "death", [level(1, 4), level(2, -30, "died")], 0, "x", 0, 26)
    assert verdicts([ruined], "reckless") == {"median net over every slip": True}
    thriving = RunLog("S", "fighter", "victory", [level(i, 9) for i in range(1, 6)], 90, "x", 0, 0)
    assert verdicts([thriving], "reckless") == {"median net over every slip": False}
