"""Saving on screen (M8): the Esc menu, Save & quit at the desk, the autosave at check-in, and
what death and victory do to the save and the personnel file."""

from pathlib import Path

import pytest
from textual.pilot import Pilot

from minetoofar.core.seed import Seed
from minetoofar.persist.errors import SaveError
from minetoofar.persist.records import RECORDS_FILE, read_records
from minetoofar.persist.save import SAVE_FILE, SavedRun, has_save, load_save, write_save
from minetoofar.sim.bot import play
from minetoofar.sim.game import Game
from minetoofar.ui.game_app import (
    ConfirmScreen,
    DeathScreen,
    DeskScreen,
    GameApp,
    MenuScreen,
    ReviewScreen,
    SlipScreen,
)
from tests.helpers import BALANCE
from tests.ui.test_game_app import run_app, text
from tests.ui.test_game_fight import doomed_game

BASE = BALANCE.economy.base_fee  # the Base Job Fee as shipped

SEED = Seed.parse("GOLD0012")


def owned(game: Game, folder: Path) -> GameApp:
    return GameApp(game, "unicode", saves=folder, owns_slot=True)


def at_exit(level: int = 1) -> Game:
    g = Game.new(SEED, level)
    g.player.pos = g.spec.exit
    return g


def a_save(folder: Path) -> None:
    g = Game.new(SEED, 1)
    g.check_out()
    write_save(folder, SavedRun(SEED.canonical, "fighter", 1, 2, g.carry_over(), None, []))


# -- the Esc menu ----------------------------------------------------------------------


def test_escape_opens_the_menu_and_escape_closes_it_again(tmp_path: Path) -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        before = app.game.state_hash()
        await pilot.press("escape")
        assert isinstance(app.screen, MenuScreen)
        shown = str(app.screen.query_one("#menu").render())
        assert app.text.line("menu_save") in shown and app.text.line("menu_back") in shown
        await pilot.press("escape")
        assert not isinstance(app.screen, MenuScreen)
        assert app.game.state_hash() == before and not has_save(tmp_path)

    run_app(owned(Game.new(SEED, 1), tmp_path), (80, 24), body)


def test_save_and_quit_writes_the_level_in_play_and_leaves(tmp_path: Path) -> None:
    game = Game.new(SEED, 2, rank=3)
    play(game, game.submit, 60)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("escape", "s")
        await pilot.pause()
        assert not app.is_running

    run_app(owned(game, tmp_path), (80, 24), body)
    saved = load_save(tmp_path)
    assert saved.game is not None and saved.game.state_hash() == game.state_hash()
    assert saved.level == 2 and saved.log and saved.log[0].startswith("Work Order 2")


def test_a_saved_level_resumes_where_it_was_with_its_log(tmp_path: Path) -> None:
    game = Game.new(SEED, 2, rank=3)
    play(game, game.submit, 60)
    hero = game.view().hero
    write_save(tmp_path, SavedRun(SEED.canonical, "fighter", 3, 2, None, game, ["one", "two"]))
    saved = load_save(tmp_path)
    assert saved.game is not None

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert app.game.state_hash() == game.state_hash()
        assert app.messages[:2] == ["one", "two"]
        assert app.messages[-1] == app.text.line("resumed")
        assert f"{hero.hp}/{hero.max_hp}" in text(app, "#status")
        before = app.game.ticks
        await pilot.press("full_stop")
        assert app.game.ticks == before + 100

    run_app(GameApp(saved.game, "unicode", saves=tmp_path, resume=saved), (80, 24), body)


def test_a_run_started_from_the_command_line_asks_before_replacing_a_save(tmp_path: Path) -> None:
    a_save(tmp_path)
    before = (tmp_path / SAVE_FILE).read_bytes()

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("escape", "s")
        assert isinstance(app.screen, ConfirmScreen) and app.is_running
        assert "replaces the run already saved" in str(app.screen.query_one("#menu").render())
        await pilot.press("n")
        assert (tmp_path / SAVE_FILE).read_bytes() == before and app.is_running
        await pilot.press("escape", "s", "y")
        await pilot.pause()
        assert not app.is_running

    run_app(GameApp(Game.new(SEED, 1), "unicode", saves=tmp_path), (80, 24), body)
    assert load_save(tmp_path).game is not None  # now it is this run


def test_a_failed_save_says_why_and_the_run_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(folder: Path, run: SavedRun) -> None:
        raise SaveError("the disk is full")

    monkeypatch.setattr("minetoofar.ui.game_app.write_save", boom)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("escape", "s")
        await pilot.pause()
        assert app.is_running
        assert app.messages[-1] == app.text.line("save_failed", message="the disk is full")

    run_app(owned(Game.new(SEED, 1), tmp_path), (80, 24), body)


def test_without_a_save_folder_nothing_is_ever_written(tmp_path: Path) -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("escape", "s")
        await pilot.pause()
        assert app.is_running  # nowhere to save to, so there is nothing to quit for

    run_app(GameApp(Game.new(SEED, 1), "unicode"), (80, 24), body)


# -- the desk --------------------------------------------------------------------------


async def to_the_desk(pilot: Pilot[None]) -> None:
    await pilot.press("greater_than_sign", "enter", "enter", "enter")
    await pilot.pause()


def test_save_and_quit_at_the_desk_keeps_what_was_bought_and_arrives_on_the_next_level(
    tmp_path: Path,
) -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await to_the_desk(pilot)
        assert isinstance(app.screen, DeskScreen)
        app.screen.checkin.stock[0] = "wellness_seminar"
        await pilot.press("1", "s")
        await pilot.pause()
        assert not app.is_running

    run_app(owned(at_exit(), tmp_path), (80, 40), body)
    saved = load_save(tmp_path)
    assert saved.level == 2 and saved.game is None and saved.arrival is not None
    assert saved.arrival.player.hp_bonus == 3 and saved.arrival.player.rank == 2
    assert saved.arrival.account.wallet == BASE - 10 and saved.arrival.cleared == 1


def test_leaving_the_desk_saves_the_run_before_going_down(tmp_path: Path) -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await to_the_desk(pilot)
        assert not has_save(tmp_path)
        await pilot.press("enter")
        await pilot.pause()
        assert app.game.spec.level == 2 and has_save(tmp_path)

    run_app(owned(at_exit(), tmp_path), (80, 40), body)
    saved = load_save(tmp_path)
    assert saved.level == 2 and saved.game is None and saved.arrival is not None


def test_a_check_in_save_resumes_on_the_next_level_with_the_kit(tmp_path: Path) -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await to_the_desk(pilot)
        await pilot.press("enter")

    run_app(owned(at_exit(), tmp_path), (80, 40), body)
    saved = load_save(tmp_path)
    game = Game.new(SEED, saved.level, carry=saved.arrival)

    async def resumed(app: GameApp, pilot: Pilot[None]) -> None:
        assert app.game.spec.level == 2 and app.game.player.rank == 2
        assert app.game.account.wallet == BASE and app.game.cleared == 1

    run_app(GameApp(game, "unicode", saves=tmp_path, resume=saved), (80, 24), resumed)


def test_the_autosave_never_overwrites_a_run_that_is_not_yours(tmp_path: Path) -> None:
    a_save(tmp_path)
    before = (tmp_path / SAVE_FILE).read_bytes()

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await to_the_desk(pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert app.game.spec.level == 2

    run_app(GameApp(at_exit(), "unicode", saves=tmp_path), (80, 40), body)
    assert (tmp_path / SAVE_FILE).read_bytes() == before


# -- death and victory -----------------------------------------------------------------


def die(folder: Path, game: Game, owns: bool = True) -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        for _ in range(60):
            if isinstance(app.screen, DeathScreen):
                return
            await pilot.press("enter" if isinstance(app.screen, SlipScreen) else "full_stop")
            await pilot.pause()
        raise AssertionError("the Fighter never died")

    run_app(GameApp(game, "unicode", saves=folder, owns_slot=owns), (80, 40), body)


def test_death_deletes_the_save_and_files_a_record(tmp_path: Path) -> None:
    a_save(tmp_path)
    die(tmp_path, doomed_game())
    assert not has_save(tmp_path)
    (record,) = read_records(tmp_path)
    assert record.outcome == "death" and record.cause == "Shambling Miner"
    assert record.class_id == "fighter" and record.seed == "1:BRASSLAMP42"


def test_a_run_that_is_not_yours_dies_without_taking_your_save_with_it(tmp_path: Path) -> None:
    a_save(tmp_path)
    die(tmp_path, doomed_game(), owns=False)
    assert has_save(tmp_path) and len(read_records(tmp_path)) == 1


def test_victory_deletes_the_save_and_files_a_record(tmp_path: Path) -> None:
    a_save(tmp_path)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign", "enter", "enter")
        await pilot.pause()
        assert isinstance(app.screen, ReviewScreen)

    run_app(owned(at_exit(5), tmp_path), (80, 40), body)
    assert not has_save(tmp_path)
    (record,) = read_records(tmp_path)
    assert record.outcome == "victory" and record.cause == "" and record.level == 5


def test_a_damaged_personnel_file_is_reported_on_the_report_and_the_game_carries_on(
    tmp_path: Path,
) -> None:
    (tmp_path / RECORDS_FILE).write_text("garbage")

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        for _ in range(60):
            if isinstance(app.screen, DeathScreen):
                break
            await pilot.press("enter" if isinstance(app.screen, SlipScreen) else "full_stop")
            await pilot.pause()
        assert "personnel file" in str(app.screen.query_one("#death").render())

    run_app(owned(doomed_game(), tmp_path), (80, 40), body)
    assert (tmp_path / RECORDS_FILE).read_text() == "garbage"
