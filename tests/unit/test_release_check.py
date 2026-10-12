"""The checks a built EXE runs on itself (M10): a whole bot-played run, and a save that another
build can read. The EXE and the source must print the very same lines."""

from pathlib import Path

import pytest

from minetoofar.__main__ import main
from minetoofar.core.seed import Seed
from minetoofar.persist.errors import SaveError
from minetoofar.persist.save import has_save
from minetoofar.release_check import autoplay_line, read_save_line, write_save_line
from minetoofar.sim.autoplay import play_run

SEED = Seed.parse("SIM0007")


def test_the_autoplay_line_reports_the_run_the_bot_plays() -> None:
    run = play_run(SEED, "fighter")
    assert autoplay_line(SEED, "fighter") == (
        f"autoplay ok: seed 1:SIM0007 fighter {run.outcome} levels {len(run.levels)} "
        f"score {run.score} title {run.title} wallet {run.wallet} debt {run.debt}"
    )


def test_the_autoplay_line_is_the_same_every_time() -> None:
    assert autoplay_line(SEED, "rogue") == autoplay_line(Seed.parse("1:SIM0007"), "rogue")


def test_a_written_save_reads_back_with_the_same_state(tmp_path: Path) -> None:
    written = write_save_line(SEED, "ranger", tmp_path)
    assert has_save(tmp_path) and written.startswith("save written: seed 1:SIM0007 ranger")
    read = read_save_line(tmp_path)
    assert read == written.replace("save written:", "save ok:")


def test_the_save_is_made_in_the_middle_of_a_level(tmp_path: Path) -> None:
    line = write_save_line(SEED, "fighter", tmp_path)
    assert " level 1 " in line and "turn 0 " not in line


def test_reading_a_missing_save_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(SaveError):
        read_save_line(tmp_path)


def test_reading_a_damaged_save_fails_loudly(tmp_path: Path) -> None:
    write_save_line(SEED, "fighter", tmp_path)
    (tmp_path / "run.json").write_text("{ not json")
    with pytest.raises(SaveError):
        read_save_line(tmp_path)


# -- the command line ----------------------------------------------------------------------------


def test_autoplay_flag_prints_the_line(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--autoplay", "--seed", "SIM0007", "--class", "fighter"]) == 0
    assert capsys.readouterr().out.strip() == autoplay_line(SEED, "fighter")


def test_save_selftest_writes_then_reads(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = ["--seed", "SIM0007", "--class", "rogue", "--save-dir", str(tmp_path)]
    assert main([*base, "--save-selftest", "write"]) == 0
    written = capsys.readouterr().out.strip()
    assert main([*base, "--save-selftest", "read"]) == 0
    assert capsys.readouterr().out.strip() == written.replace("save written:", "save ok:")


def test_reading_a_missing_save_through_the_flag_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--save-dir", str(tmp_path), "--save-selftest", "read"]) == 2
    assert "minetoofar:" in capsys.readouterr().err
