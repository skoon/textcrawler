from pathlib import Path

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
        main(["--seed", "A", "--stage", "nonesuch", "--hash"])
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started: list[tuple[str, str, int, str, int, str]] = []
    monkeypatch.setattr(
        "minetoofar.ui.game_app.run",
        lambda seed, level, glyphs, rank, class_id, saves=None, owns_slot=False: started.append(
            ("game", seed.canonical, level, glyphs, rank, class_id)
        ),
    )
    monkeypatch.setattr(
        "minetoofar.ui.app.run_viewer",
        lambda seed, level, glyphs: started.append(("view", seed.canonical, level, glyphs, 1, "")),
    )
    base = ["--seed", "BRASSLAMP42", "--save-dir", str(tmp_path)]
    assert main([*base, "--level", "2", "--glyphs", "ascii", "--class", "rogue"]) == 0
    assert main([*base, "--view", "--glyphs", "unicode"]) == 0
    assert main([*base, "--rank", "4", "--glyphs", "ascii", "--class", "ranger"]) == 0
    assert started == [
        ("game", "BRASSLAMP42", 2, "ascii", 1, "rogue"),
        ("view", "BRASSLAMP42", 1, "unicode", 1, ""),
        ("game", "BRASSLAMP42", 1, "ascii", 4, "ranger"),
    ]


def test_without_a_class_the_select_screen_picks_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started: list[str] = []
    monkeypatch.setattr("minetoofar.ui.select.choose_class", lambda: "ranger")
    monkeypatch.setattr(
        "minetoofar.ui.game_app.run",
        lambda seed, level, glyphs, rank, class_id, saves=None, owns_slot=False: started.append(
            class_id
        ),
    )
    assert main(["--seed", "BRASSLAMP42", "--glyphs", "ascii", "--save-dir", str(tmp_path)]) == 0
    assert started == ["ranger"]


def test_quitting_the_select_screen_starts_no_game(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started: list[str] = []
    monkeypatch.setattr("minetoofar.ui.select.choose_class", lambda: None)
    monkeypatch.setattr("minetoofar.ui.game_app.run", lambda *args: started.append("started"))
    assert main(["--seed", "BRASSLAMP42", "--glyphs", "ascii", "--save-dir", str(tmp_path)]) == 0
    assert started == []


# -- the title menu: a plain launch ------------------------------------------------------------


def plain(tmp_path: Path) -> list[str]:
    return ["--glyphs", "ascii", "--save-dir", str(tmp_path)]


def test_a_plain_launch_opens_the_title_menu_and_quit_starts_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started: list[str] = []
    monkeypatch.setattr("minetoofar.ui.title.choose_start", lambda folder: ("quit", None))
    monkeypatch.setattr("minetoofar.ui.game_app.run", lambda *args, **kw: started.append("run"))
    assert main(plain(tmp_path)) == 0 and started == []


def test_new_run_picks_a_class_and_owns_the_save_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started: list[tuple[int, int, str, bool, Path | None]] = []
    monkeypatch.setattr("minetoofar.ui.title.choose_start", lambda folder: ("new", None))
    monkeypatch.setattr("minetoofar.ui.select.choose_class", lambda: "rogue")

    def fake(seed, level, glyphs, rank, class_id, saves=None, owns_slot=False):  # type: ignore[no-untyped-def]
        started.append((level, rank, class_id, owns_slot, saves))

    monkeypatch.setattr("minetoofar.ui.game_app.run", fake)
    assert main(plain(tmp_path)) == 0
    assert started == [(1, 1, "rogue", True, tmp_path)]


def test_continue_hands_the_saved_run_to_the_game(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sentinel = object()
    got: list[object] = []
    monkeypatch.setattr("minetoofar.ui.title.choose_start", lambda folder: ("continue", sentinel))
    monkeypatch.setattr(
        "minetoofar.ui.game_app.run_saved", lambda saved, glyphs, saves: got.append((saved, saves))
    )
    assert main(plain(tmp_path)) == 0
    assert got == [(sentinel, tmp_path)]


def test_backing_out_of_the_class_screen_returns_to_the_title_menu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    menus = iter([("new", None), ("quit", None)])
    monkeypatch.setattr("minetoofar.ui.title.choose_start", lambda folder: next(menus))
    monkeypatch.setattr("minetoofar.ui.select.choose_class", lambda: None)
    assert main(plain(tmp_path)) == 0


def test_an_unknown_class_is_rejected() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--seed", "A", "--class", "wizard"])
    assert exc.value.code == 2


@pytest.mark.parametrize("rank", ["0", "6", "-1"])
def test_rank_outside_one_to_five_is_rejected(rank: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--seed", "A", "--rank", rank])
    assert exc.value.code == 2


def test_an_unusable_save_dir_stops_the_game_with_a_clear_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    code = main(["--seed", "A", "--save-dir", str(blocker / "saves")])
    assert code == 2
    assert "cannot use the save folder" in capsys.readouterr().err


def test_save_dir_is_a_known_option() -> None:
    from minetoofar.__main__ import _parser

    assert _parser().parse_args(["--save-dir", "somewhere"]).save_dir == "somewhere"


def test_where_prints_the_save_folder_without_touching_the_disk(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "not" / "yet"
    assert main(["--where", "--save-dir", str(target)]) == 0
    assert capsys.readouterr().out.strip() == str(target) and not target.exists()
