"""The title menu (M8): Continue, New run, Quit; a bad save is reported and starts nothing."""

import asyncio
from pathlib import Path

from minetoofar.core.seed import Seed
from minetoofar.persist.save import SAVE_FILE, SavedRun, has_save, write_save
from minetoofar.sim.game import Game
from minetoofar.ui.title import TitleApp

SEED = "GOLD0012"


def a_save(folder: Path) -> SavedRun:
    g = Game.new(Seed.parse(SEED), 1)
    g.check_out()
    run = SavedRun(SEED, "rogue", 1, 2, g.carry_over(), None, [])
    write_save(folder, run)
    return run


def drive(folder: Path, *keys: str) -> tuple[TitleApp, object]:
    app = TitleApp(folder)
    result: list[object] = []

    async def go() -> None:
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            for key in keys:
                await pilot.press(key)
                await pilot.pause()
            result.append(app.return_value)

    asyncio.run(go())
    return app, result[0]


def screen_text(app: TitleApp) -> str:
    return str(app.query_one("#title").render())


def test_with_no_save_there_is_no_continue_and_new_starts_straight_away(tmp_path: Path) -> None:
    app, got = drive(tmp_path, "n")
    assert got == ("new", None)


def test_the_menu_shows_the_title_and_hides_continue_without_a_save(tmp_path: Path) -> None:
    seen: list[str] = []

    async def go() -> None:
        app = TitleApp(tmp_path)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            seen.append(screen_text(app))
            await pilot.press("q")

    asyncio.run(go())
    text = seen[0]
    assert "A  MINE  TOO  FAR" in text and "[N] New run" in text and "[Q] Quit" in text
    assert "[C] Continue" not in text


def test_quit_returns_quit(tmp_path: Path) -> None:
    assert drive(tmp_path, "q")[1] == ("quit", None)
    assert drive(tmp_path, "escape")[1] == ("quit", None)


def test_continue_loads_the_save_and_hands_it_back(tmp_path: Path) -> None:
    saved = a_save(tmp_path)
    app, got = drive(tmp_path, "c")
    assert isinstance(got, tuple) and got[0] == "continue"
    run = got[1]
    assert isinstance(run, SavedRun) and run.level == 2 and run.class_id == "rogue"
    assert run.arrival == saved.arrival and has_save(tmp_path)  # loading keeps the file


def test_the_menu_describes_the_saved_run(tmp_path: Path) -> None:
    a_save(tmp_path)
    seen: list[str] = []

    async def go() -> None:
        app = TitleApp(tmp_path)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            seen.append(screen_text(app))
            await pilot.press("q")

    asyncio.run(go())
    assert "[C] Continue" in seen[0] and "Rogue, Work Order 2 of 5" in seen[0]
    assert "1:GOLD0012" in seen[0]


def test_a_new_run_over_a_save_asks_first_and_n_keeps_the_save(tmp_path: Path) -> None:
    a_save(tmp_path)
    app, got = drive(tmp_path, "n", "n", "q")
    assert got == ("quit", None) and has_save(tmp_path)


def test_agreeing_replaces_the_save(tmp_path: Path) -> None:
    a_save(tmp_path)
    app, got = drive(tmp_path, "n", "y")
    assert got == ("new", None) and not has_save(tmp_path)


def test_a_damaged_save_is_reported_and_continue_starts_nothing(tmp_path: Path) -> None:
    (tmp_path / SAVE_FILE).write_text("\x00" * 200)
    seen: list[str] = []

    async def go() -> None:
        app = TitleApp(tmp_path)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            seen.append(screen_text(app))
            await pilot.press("c")
            await pilot.pause()
            seen.append(str(app.is_running))
            await pilot.press("q")

    asyncio.run(go())
    assert "damaged" in seen[0] and "[C] Continue" not in seen[0]
    assert seen[1] == "True"  # still on the menu


def test_a_newer_save_is_reported_by_name(tmp_path: Path) -> None:
    import json

    a_save(tmp_path)
    data = json.loads((tmp_path / SAVE_FILE).read_text())
    data["save_version"] = 99
    (tmp_path / SAVE_FILE).write_text(json.dumps(data))
    seen: list[str] = []

    async def go() -> None:
        app = TitleApp(tmp_path)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            seen.append(screen_text(app))
            await pilot.press("q")

    asyncio.run(go())
    assert "newer version" in seen[0]


# -- the employment history ----------------------------------------------------------------------


def a_record(folder: Path) -> None:
    from minetoofar.persist.records import Record, append_record

    append_record(
        folder,
        Record("1:GOLD0012", "ranger", "death", 1, 3, 2, 31, "valued", "Foreman Grimsby", 410),
    )


def drive_screens(folder: Path, *keys: str) -> list[str]:
    """What the title screen shows before the first key and after each one."""
    seen: list[str] = []

    async def go() -> None:
        app = TitleApp(folder)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            seen.append(screen_text(app))
            for key in keys:
                await pilot.press(key)
                await pilot.pause()
                if app.is_running:
                    seen.append(screen_text(app))

    asyncio.run(go())
    return seen


def test_the_menu_offers_the_employment_history(tmp_path: Path) -> None:
    assert "[R] Employment history" in drive_screens(tmp_path)[0]


def test_r_shows_the_runs_on_file_and_escape_returns_to_the_menu(tmp_path: Path) -> None:
    a_record(tmp_path)
    menu, history, back = drive_screens(tmp_path, "r", "escape")
    assert "EMPLOYMENT HISTORY" in history and "Ranger" in history and "Foreman Grimsby" in history
    assert "[N] New run" not in history
    assert back == menu


def test_an_empty_history_says_so(tmp_path: Path) -> None:
    _, history = drive_screens(tmp_path, "r")
    assert "No runs on file." in history


def test_a_damaged_records_file_is_reported_not_fatal(tmp_path: Path) -> None:
    (tmp_path / "records.json").write_text("{ not json")
    _, history = drive_screens(tmp_path, "r")
    assert "damaged" in history


def test_the_menu_keys_still_work_after_looking_at_the_history(tmp_path: Path) -> None:
    app, got = drive(tmp_path, "r", "escape", "n")
    assert got == ("new", None)
