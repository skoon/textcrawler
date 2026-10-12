"""A whole run through the screens: five levels, four check-ins, the review, and the paperwork."""

from pathlib import Path

from textual.pilot import Pilot

from minetoofar.content.balance import LEVELS
from minetoofar.content.text import load_text
from minetoofar.core.seed import Seed
from minetoofar.persist.records import read_records
from minetoofar.persist.save import has_save
from minetoofar.sim.game import Game
from minetoofar.ui.game_app import (
    DeskScreen,
    GameApp,
    MemoScreen,
    ReportScreen,
    ReviewScreen,
    SlipScreen,
)
from minetoofar.ui.personnel import record_lines
from tests.ui.test_game_app import run_app

PAPERWORK = (ReportScreen, SlipScreen, MemoScreen, DeskScreen)


async def sign_everything(app: GameApp, pilot: Pilot[None]) -> None:
    for _ in range(12):
        if not isinstance(app.screen, (*PAPERWORK, ReviewScreen)):
            return
        if isinstance(app.screen, ReviewScreen):
            return
        await pilot.press("enter")
        await pilot.pause()
    raise AssertionError("the paperwork never ended")


def test_five_levels_end_in_the_review_and_the_personnel_file(tmp_path: Path) -> None:
    game = Game.new(Seed.parse("GOLD0012"), 1)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        for level in range(1, LEVELS + 1):
            assert app.game.spec.level == level and app.game.player.rank == level
            app.game.player.pos = app.game.spec.exit  # as if it had been walked
            await pilot.press("greater_than_sign")
            await pilot.pause()
            await sign_everything(app, pilot)
            if level < LEVELS:
                assert has_save(tmp_path), "the check-in autosaves"
        assert isinstance(app.screen, ReviewScreen)

    run_app(GameApp(game, "unicode", saves=tmp_path, owns_slot=True), (80, 40), body)
    assert not has_save(tmp_path)
    (record,) = read_records(tmp_path)
    assert record.outcome == "victory" and record.cleared == LEVELS and record.level == LEVELS
    assert record.score > 0 and record.seed == "1:GOLD0012"
    shown = "\n".join(record_lines([record], load_text()))
    assert "1:GOLD0012" in shown
