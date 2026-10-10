"""M5 screens: the graveyard palette, wrapped speech, the Brine prompt, and going down."""

from textual.pilot import Pilot

from minetoofar.core.grid import Tile
from minetoofar.core.seed import Seed
from minetoofar.sim.game import Game
from minetoofar.ui.game_app import GameApp
from minetoofar.ui.mapview import GRAVEYARD_STYLES, STYLES, MapView
from tests.helpers import make_game
from tests.ui.test_game_app import run_app, text

HALL = ["#" * 10, "#<.~~..>.#", "#" * 10]


def cell_style(app: GameApp, x: int, y: int) -> object:
    view = app.query_one(MapView)
    return view.row_cells(y - view.cam_y)[x - view.cam_x][1]


def test_graveyard_floors_swap_the_floor_and_wall_colours_only() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert cell_style(app, 2, 1) == GRAVEYARD_STYLES[Tile.FLOOR] != STYLES[Tile.FLOOR]
        assert cell_style(app, 0, 1) == GRAVEYARD_STYLES[Tile.WALL] != STYLES[Tile.WALL]
        assert cell_style(app, 3, 1) == STYLES[Tile.BRINE]  # everything else keeps its colour

    run_app(GameApp(make_game(HALL, graveyard=True), "unicode"), (80, 24), body)


def test_a_normal_floor_keeps_the_mine_palette() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert cell_style(app, 2, 1) == STYLES[Tile.FLOOR]

    run_app(GameApp(make_game(HALL), "unicode"), (80, 24), body)


def test_a_long_line_wraps_onto_a_second_log_row() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        said = "word " * 30
        app._say(said.strip())
        shown = text(app, "#log").split("\n")
        assert len(shown) >= 3 and any(row.startswith("  ") for row in shown)
        assert all(len(row) <= app.query_one("#log").size.width for row in shown)

    run_app(GameApp(make_game(HALL), "unicode"), (80, 24), body)


def test_stepping_into_brine_with_a_lit_torch_asks_first() -> None:
    game = make_game(HALL)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("t", "l")  # light the torch, step to (2,1)
        await pilot.press("l")  # the Brine is next
        assert app.game.pos.x == 2 and app.messages[-1] == app.text.line("brine_prompt")
        await pilot.press("n")  # anything but y declines
        assert app.game.pos.x == 2 and app.pending is None
        await pilot.press("l", "y")
        assert app.game.pos.x == 3

    run_app(GameApp(game, "unicode"), (80, 24), body)


def test_brine_with_the_torch_out_needs_no_prompt() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l", "l")
        assert app.game.pos.x == 3 and app.pending is None

    run_app(GameApp(make_game(HALL), "unicode"), (80, 24), body)


def test_descend_off_the_down_shaft_is_refused() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign")
        assert app.messages[-1] == app.text.line("descend_none")
        assert app.game.spec.level == 1 and app.game.ticks == 0

    run_app(GameApp(make_game(HALL), "unicode"), (80, 24), body)


def descend_to_exit(app: GameApp) -> None:
    app.game.player.pos = app.game.spec.exit


def test_descend_on_the_down_shaft_starts_the_next_level_with_rank_and_armour() -> None:
    game = Game.new(Seed.parse("BRASSLAMP42"), 1, rank=3)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        descend_to_exit(app)
        app.game.player.body_dur -= 2
        worn = app.game.player.body_dur
        await pilot.press("greater_than_sign")
        await pilot.pause()
        assert app.game.spec.level == 2 and app.game.spec.seed == "BRASSLAMP42"
        assert app.game.player.rank == 3 and app.game.player.body_dur == worn
        assert app.game.player.hp == app.game.player.max_hp
        assert app.query_one(MapView).border_title == "Stamp Mill and Assay Floor · L2"
        assert "Work Order 2 of 5" in app.messages[-1] and len(app.messages) == 1

    run_app(GameApp(game, "unicode"), (80, 24), body)


def test_enter_also_descends() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        descend_to_exit(app)
        await pilot.press("enter")
        await pilot.pause()
        assert app.game.spec.level == 2

    run_app(GameApp(Game.new(Seed.parse("BRASSLAMP42"), 1), "unicode"), (80, 24), body)


def test_f5_skips_a_level_from_anywhere() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("f5")
        await pilot.pause()
        assert app.game.spec.level == 2 and app.game.pos == app.game.spec.entry

    run_app(GameApp(Game.new(Seed.parse("BRASSLAMP42"), 1), "unicode"), (80, 24), body)


def test_the_last_level_has_nowhere_to_descend() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        descend_to_exit(app)
        await pilot.press("greater_than_sign")
        await pilot.press("f5")
        assert app.game.spec.level == 5
        assert app.messages[-1] == app.text.line("descend_last")

    run_app(GameApp(Game.new(Seed.parse("BRASSLAMP42"), 5), "unicode"), (80, 24), body)


def test_retry_after_descending_restarts_the_level_you_died_on_with_the_armour_you_arrived_in() -> (
    None
):
    game = Game.new(Seed.parse("BRASSLAMP42"), 1)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        app.game.player.body_dur -= 3
        arrived = app.game.player.body_dur
        await pilot.press("f5")
        await pilot.pause()
        app.game.player.body_dur = 0  # wrecked on level 2
        app.game.player.hp = 0
        app.game.dead = True
        app._report_death()
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.game.spec.level == 2 and app.game.player.body_dur == arrived

    run_app(GameApp(game, "unicode"), (80, 24), body)
