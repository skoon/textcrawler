"""The help screen (GDD 4.1): `?` lists the keys and the rules of the job; any key closes it."""

from textual.pilot import Pilot

from minetoofar.core.geometry import Pos
from minetoofar.ui.game_app import GameApp, HelpScreen
from minetoofar.ui.keymap import BINDINGS, UiAction
from tests.helpers import make_game
from tests.ui.test_game_app import run_app

HALL = ["#" * 12, "#<.........#", "#" * 12]


def on(game: object, body: object) -> None:
    run_app(GameApp(game, "unicode"), (80, 24), body)  # type: ignore[arg-type]


def test_the_question_mark_is_bound_to_help() -> None:
    assert BINDINGS["?"] is UiAction.HELP


def test_question_mark_opens_help_and_any_key_closes_it_without_moving() -> None:
    game = make_game(HALL)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("question_mark")
        assert isinstance(app.screen, HelpScreen)
        panel = app.screen.query_one("#help")
        assert panel.border_title == app.text.line("help_title")
        await pilot.press("l")
        assert not isinstance(app.screen, HelpScreen) and app.game.pos == Pos(1, 1)

    on(game, body)


def test_help_names_every_key_the_game_answers_to() -> None:
    game = make_game(HALL)
    keys = ("Esc", "F2", "Ctrl+L", "Shift+Q", "Enter", "Space")
    letters = ("a", "t", "g", "i", "e", "q", "d", "x", "c", "?")

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("question_mark")
        shown = str(app.screen.query_one("#help").render())
        for key in keys:
            assert key in shown, key
        for letter in letters:
            assert f"{letter}  " in shown or f"{letter} " in shown, letter
        for rule in ("Down Shaft", "Requisitions Desk", "debt"):
            assert rule in shown, rule

    on(game, body)


def test_help_fits_an_80_by_24_terminal() -> None:
    game = make_game(HALL)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("question_mark")
        panel = app.screen.query_one("#help")
        assert panel.region.height <= 24 and panel.region.width <= 80
        assert panel.region.y >= 0

    on(game, body)


def test_escape_closes_help_rather_than_opening_the_menu() -> None:
    game = make_game(HALL)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("question_mark", "escape")
        assert not isinstance(app.screen, HelpScreen)
        assert app.game.pos == Pos(1, 1)

    on(game, body)


def test_no_help_line_is_wider_than_the_panel_so_nothing_wraps() -> None:
    from minetoofar.content.text import load_text

    width = 68 - 2 - 4  # the #help panel: its width less border and padding
    lines = load_text().line("help_text").splitlines()
    assert [line for line in lines if len(line) > width] == []
