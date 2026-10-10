import pytest

from minetoofar import __version__
from minetoofar.__main__ import main
from minetoofar.core.seed import GEN_VERSION, Seed
from minetoofar.gen.layout import generate_level
from minetoofar.gen.world import STAGES, generate_world


def test_version_reports_game_and_generator(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    out = capsys.readouterr().out
    assert __version__ in out and f"generator {GEN_VERSION}" in out


def test_hash_prints_the_levelspec_sha(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--seed", "brass-lamp-42", "--level", "3", "--hash"]) == 0
    expected = generate_level(Seed.parse("BRASSLAMP42"), 3).sha256
    assert capsys.readouterr().out == expected + "\n"


def test_dump_prints_the_canonical_dump(capsysbinary: pytest.CaptureFixture[bytes]) -> None:
    assert main(["--seed", "BRASSLAMP42", "--level", "1", "--dump"]) == 0
    out = capsysbinary.readouterr().out
    assert out == generate_level(Seed.parse("BRASSLAMP42"), 1).dump().encode("ascii")


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_dumps_and_hashes_through_the_cli(
    stage: str, capsys: pytest.CaptureFixture[str]
) -> None:
    out = generate_world(Seed.parse("BRASSLAMP42"), 2).stage(stage)
    assert main(["--seed", "BRASSLAMP42", "--level", "2", "--stage", stage, "--hash"]) == 0
    assert capsys.readouterr().out == out.sha256 + "\n"
    assert main(["--seed", "BRASSLAMP42", "--level", "2", "--stage", stage, "--dump"]) == 0
    assert capsys.readouterr().out == out.dump()


def test_unknown_stage_is_rejected() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--seed", "A", "--stage", "loot", "--hash"])
    assert exc.value.code == 2


def test_share_code_is_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--seed", f"{GEN_VERSION}:BRASSLAMP42", "--level", "2", "--hash"]) == 0
    assert capsys.readouterr().out.strip() == generate_level(Seed.parse("BRASSLAMP42"), 2).sha256


def test_bad_seed_fails_loudly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--seed", "not valid!", "--hash"])
    assert exc.value.code == 2
    assert "seed" in capsys.readouterr().err


def test_level_out_of_range_fails_loudly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--seed", "A", "--level", "9", "--hash"])
    assert exc.value.code == 2


def test_glyph_test_lists_both_sets(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--glyph-test"]) == 0
    out = capsys.readouterr().out
    assert "Gravedigger Skeleton" in out and "Ξ" in out and "unicode" in out and "ascii" in out


def test_ui_selftest_runs_the_game_headless(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--ui-selftest", "--seed", "BRASSLAMP42", "--level", "2"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("ui ok") and "1:BRASSLAMP42" in out and "Level 2" in out


def test_default_launch_starts_the_game_and_view_starts_the_map_viewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[tuple[str, str, int, str, int, str]] = []
    monkeypatch.setattr(
        "minetoofar.ui.game_app.run",
        lambda seed, level, glyphs, rank, class_id: started.append(
            ("game", seed.canonical, level, glyphs, rank, class_id)
        ),
    )
    monkeypatch.setattr(
        "minetoofar.ui.app.run_viewer",
        lambda seed, level, glyphs: started.append(("view", seed.canonical, level, glyphs, 1, "")),
    )
    base = ["--seed", "BRASSLAMP42"]
    assert main([*base, "--level", "2", "--glyphs", "ascii", "--class", "rogue"]) == 0
    assert main([*base, "--view", "--glyphs", "unicode"]) == 0
    assert main([*base, "--rank", "4", "--glyphs", "ascii", "--class", "ranger"]) == 0
    assert started == [
        ("game", "BRASSLAMP42", 2, "ascii", 1, "rogue"),
        ("view", "BRASSLAMP42", 1, "unicode", 1, ""),
        ("game", "BRASSLAMP42", 1, "ascii", 4, "ranger"),
    ]


def test_without_a_class_the_select_screen_picks_one(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[str] = []
    monkeypatch.setattr("minetoofar.ui.select.choose_class", lambda: "ranger")
    monkeypatch.setattr(
        "minetoofar.ui.game_app.run",
        lambda seed, level, glyphs, rank, class_id: started.append(class_id),
    )
    assert main(["--seed", "BRASSLAMP42", "--glyphs", "ascii"]) == 0
    assert started == ["ranger"]


def test_quitting_the_select_screen_starts_no_game(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[str] = []
    monkeypatch.setattr("minetoofar.ui.select.choose_class", lambda: None)
    monkeypatch.setattr("minetoofar.ui.game_app.run", lambda *args: started.append("started"))
    assert main(["--seed", "BRASSLAMP42", "--glyphs", "ascii"]) == 0
    assert started == []


def test_an_unknown_class_is_rejected() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--seed", "A", "--class", "wizard"])
    assert exc.value.code == 2


@pytest.mark.parametrize("rank", ["0", "6", "-1"])
def test_rank_outside_one_to_five_is_rejected(rank: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--seed", "A", "--rank", rank])
    assert exc.value.code == 2
