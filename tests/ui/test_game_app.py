import asyncio
from collections.abc import Awaitable, Callable

import pytest
from textual.geometry import Region
from textual.pilot import Pilot
from textual.widgets import Static

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.core.seed import Seed
from minetoofar.ui.game_app import GameApp, log_lines, selftest
from minetoofar.ui.mapview import DIM_STYLES, STYLES, MapView
from tests.helpers import make_game
from tests.scenario.test_walk import empty_level, route

VI = {(1, 0): "l", (-1, 0): "h", (0, 1): "j", (0, -1): "k", (1, 1): "n", (-1, 1): "b",
      (1, -1): "u", (-1, -1): "y"}  # fmt: skip
CORRIDOR = ["#" * 30, "#<" + "." * 27 + "#", "#" * 30]
DOOR_ROOM = ["#########", "#<..+...#", "#########"]

Body = Callable[[GameApp, Pilot[None]], Awaitable[None]]


def run_app(app: GameApp, size: tuple[int, int], body: Body) -> None:
    async def go() -> None:
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await body(app, pilot)

    asyncio.run(go())


def on_map(rows: list[str], size: tuple[int, int], body: Body, glyphs: str = "unicode") -> None:
    run_app(GameApp(make_game(rows), glyphs), size, body)


def on_level(seed: str, level: int, size: tuple[int, int], body: Body) -> None:
    run_app(GameApp(empty_level(seed, level), "unicode"), size, body)


def text(app: GameApp, selector: str) -> str:
    return str(app.query_one(selector, Static).content)


def painted(app: GameApp) -> list[str]:
    """What the terminal gets: the widget's rendered lines, cache included."""
    view = app.query_one(MapView)
    return [
        strip.text for strip in view.render_lines(Region(0, 0, view.size.width, view.size.height))
    ]


def rows(app: GameApp) -> list[str]:
    view = app.query_one(MapView)
    return [view.row_text(y) for y in range(view.size.height)]


def test_opens_on_the_entry_stairs_with_a_welcome_line() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view = app.query_one(MapView)
        assert app.game.pos == app.game.spec.entry
        assert any("@" in row for row in rows(app))
        assert view.border_title == "Upper Galleries · L1"
        assert "Work Order 1 of 5: Light Housekeeping" in app.messages[0]
        assert "1:BRASSLAMP42" in text(app, "#status")

    on_level("BRASSLAMP42", 1, (80, 24), body)


@pytest.mark.parametrize(("seed", "level"), [("BRASSLAMP42", 3), ("GOLD0007", 5), ("GOLD0042", 2)])
def test_the_player_is_on_screen_when_the_game_opens(seed: str, level: int) -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view, p = app.query_one(MapView), app.game.pos
        assert view.cam_x <= p.x < view.cam_x + view.size.width
        assert view.cam_y <= p.y < view.cam_y + view.size.height
        assert any("@" in row for row in rows(app))
        assert any("@" in row for row in painted(app))

    on_level(seed, level, (80, 24), body)


def test_panels_have_the_layout_sizes_from_the_gdd() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert app.query_one("#status").outer_size.width == 28
        assert app.query_one(MapView).size == (50, 16)
        assert app.query_one("#log").outer_size.height == log_lines(24) + 2

    on_level("BRASSLAMP42", 1, (80, 24), body)


def test_log_height_grows_with_the_terminal_between_four_and_ten_lines() -> None:
    assert [log_lines(r) for r in (24, 30, 36, 48, 60, 100)] == [4, 5, 6, 8, 10, 10]


def test_log_panel_grows_on_a_tall_terminal() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert app.query_one("#log").outer_size.height == 12

    on_level("BRASSLAMP42", 1, (100, 60), body)


def test_vi_and_arrow_keys_step_one_tile() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l")
        assert app.game.pos == Pos(2, 1)
        await pilot.press("right")
        assert app.game.pos == Pos(3, 1)
        await pilot.press("h")
        assert app.game.pos == Pos(2, 1) and "Turn 3" in text(app, "#status")

    on_map(CORRIDOR, (80, 24), body)


def test_shift_vi_key_runs() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("L")
        assert app.game.pos == Pos(28, 1)

    on_map(CORRIDOR, (80, 24), body)


def test_bumping_a_wall_logs_a_refusal_and_costs_nothing() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("h")
        assert app.game.ticks == 0
        assert app.messages[-1] == app.text.line("blocked_wall")

    on_map(CORRIDOR, (80, 24), body)


def test_bumping_a_door_opens_it_and_draws_it_open() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l", "l", "l")
        assert app.messages[-1] == app.text.line("door_opened")
        assert "/" in rows(app)[1] and "+" not in rows(app)[1]

    on_map(DOOR_ROOM, (80, 24), body)


def test_fog_unseen_is_blank_and_remembered_is_dimmer_than_visible() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view = app.query_one(MapView)
        floor_row = view.row_cells(1)
        assert floor_row[6][0] == " "  # radius 4 from x=1 reaches x=5; x=6 was never lit
        await pilot.press("L")
        floor_row = view.row_cells(1)
        assert floor_row[2][1] == DIM_STYLES[Tile.FLOOR] != STYLES[Tile.FLOOR]
        assert floor_row[27][1] == STYLES[Tile.FLOOR]
        assert floor_row[2][0] == "·"  # remembered tiles keep their glyph

    on_map(CORRIDOR, (80, 24), body)


def test_the_ascii_set_draws_the_player_and_floor_plainly() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert rows(app)[1].startswith("#@...")

    on_map(CORRIDOR, (80, 24), body, glyphs="ascii")


def test_f2_swaps_glyph_sets() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert rows(app)[1].startswith("║@··")
        await pilot.press("f2")
        assert app.glyph_name == "ascii" and rows(app)[1].startswith("#@..")

    on_map(CORRIDOR, (80, 24), body)


def test_torch_key_lights_wider_and_updates_the_panel() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert "Light: Lamp (4)" in text(app, "#status")
        await pilot.press("t")
        assert "Light: Torch 400t (8)" in text(app, "#status")
        assert rows(app)[1][1 + 8] == "·"  # lit out to radius 8
        assert app.messages[-1] == app.text.line("torch_lit", radius=8)

    on_map(CORRIDOR, (80, 24), body)


def test_wait_keys_pass_a_turn() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("space", "full_stop", "5")
        assert app.game.ticks == 300

    on_map(CORRIDOR, (80, 24), body)


def test_look_mode_moves_a_cursor_not_the_player() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view = app.query_one(MapView)
        await pilot.press("x")
        assert view.cursor == Pos(1, 1) and "Entry stairs" in (view.border_subtitle or "")
        await pilot.press("l", "l")
        assert view.cursor == Pos(3, 1) and app.game.pos == Pos(1, 1)
        assert "Floor" in (view.border_subtitle or "")
        await pilot.press("k", "k")  # onto the wall row, then the level edge stops it
        assert view.cursor == Pos(3, 0) and "Timbered wall" in (view.border_subtitle or "")
        await pilot.press("escape")
        assert view.cursor is None and not view.border_subtitle
        await pilot.press("l")
        assert app.game.pos == Pos(2, 1)

    on_map(CORRIDOR, (80, 24), body)


def test_look_says_unexplored_for_tiles_never_seen() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view = app.query_one(MapView)
        await pilot.press("x", "l", "l", "l", "l", "l", "l")
        assert view.cursor == Pos(7, 1) and "Unexplored" in (view.border_subtitle or "")
        await pilot.press("x")  # x again leaves look mode
        assert view.cursor is None

    on_map(CORRIDOR, (80, 24), body)


def test_remembered_tiles_are_labelled_when_looked_at() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view = app.query_one(MapView)
        await pilot.press("L", "x")
        for _ in range(26):
            await pilot.press("h")
        assert view.cursor == Pos(2, 1) and "remembered" in (view.border_subtitle or "")

    on_map(CORRIDOR, (80, 24), body)


def test_capital_q_asks_before_quitting() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("Q")
        assert app.messages[-1] == app.text.line("quit_prompt")
        await pilot.press("n")
        await pilot.pause()
        assert app.is_running
        await pilot.press("l")
        assert app.game.pos == Pos(2, 1)  # the prompt is gone; play continues
        await pilot.press("Q", "y")
        await pilot.pause()
        assert not app.is_running

    on_map(CORRIDOR, (80, 24), body)


def test_small_terminal_shows_the_enlarge_screen_and_ignores_play() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert app.screen.has_class("too-small")
        assert "enlarge" in text(app, "#too-small") and "60x20" in text(app, "#too-small")
        await pilot.press("l")
        assert app.game.pos == Pos(1, 1)
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert not app.screen.has_class("too-small")
        await pilot.press("l")
        assert app.game.pos == Pos(2, 1)

    on_map(CORRIDOR, (60, 20), body)


@pytest.mark.parametrize("size", [(79, 24), (80, 23)])
def test_one_short_in_either_direction_is_too_small(size: tuple[int, int]) -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert app.screen.has_class("too-small")

    on_map(CORRIDOR, size, body)


def test_resizing_never_crashes() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        for w, h in [(1, 1), (5, 3), (20, 5), (79, 23), (80, 24), (81, 25), (200, 60), (80, 100)]:
            await pilot.resize_terminal(w, h)
            await pilot.pause()
            await pilot.press("l", "h", "x", "escape")
            assert app.is_running

    on_level("BRASSLAMP42", 1, (80, 24), body)


def test_camera_keeps_the_player_on_screen_all_the_way_to_the_exit() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view = app.query_one(MapView)
        for d in route(app.game):
            before = app.game.pos
            await pilot.press(VI[d])
            if app.game.pos == before:  # a closed door: the bump opened it, step again
                await pilot.press(VI[d])
            p = app.game.pos
            assert view.cam_x <= p.x < view.cam_x + view.size.width
            assert view.cam_y <= p.y < view.cam_y + view.size.height
        assert app.game.pos == app.game.spec.exit
        assert app.messages[-1] == app.text.line("on_exit")

    on_level("BRASSLAMP42", 1, (80, 24), body)


def test_selftest_reports_the_seed_level_and_name() -> None:
    out = selftest(Seed.parse("BRASSLAMP42"), 2, "unicode")
    assert out.startswith("ui ok") and "1:BRASSLAMP42" in out and "Level 2" in out
    assert "Stamp Mill and Assay Floor" in out
    assert out.isascii()  # printed to whatever code page the console has
