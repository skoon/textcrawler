"""Done criterion (M9): every class can finish a five-level run, and a share code names the same
run again. The bot plays whole runs headlessly; SIM0007 is a seed all three classes survive."""

from dataclasses import asdict

import pytest

from minetoofar.content.balance import LEVELS
from minetoofar.core.seed import GEN_VERSION, Seed
from minetoofar.sim.autoplay import play_run

SEED = "SIM0007"


@pytest.mark.parametrize("class_id", ["fighter", "rogue", "ranger"])
def test_every_class_can_complete_a_five_level_run(class_id: str) -> None:
    run = play_run(Seed.parse(SEED), class_id)
    assert run.outcome == "victory"
    assert [lv.level for lv in run.levels] == list(range(1, LEVELS + 1))
    assert all(lv.outcome == "cleared" for lv in run.levels)
    assert run.debt == 0 and run.score >= 50 and run.wallet >= 0


def test_the_share_code_plays_out_the_same_run_again() -> None:
    plain = play_run(Seed.parse(SEED), "fighter")
    shared = play_run(Seed.parse(f"{GEN_VERSION}:{SEED}"), "fighter")
    assert asdict(plain) == asdict(shared)
