import asyncio
from collections.abc import Awaitable, Callable

from textual.widgets import Static

from minetoofar.core.seed import Seed
from minetoofar.ui.app import MapApp, MapView

SEED = Seed.parse("BRASSLAMP42")


def drive(
    size: tuple[int, int], body: Callable[[MapApp, object], Awaitable[None]], **kw: object
) -> None:
    async def go() -> None:
        app = MapApp(SEED, kw.get("level", 1), kw.get("glyphs", "unicode"))  # type: ignore[arg-type]
        async with app.run_test(size=size) as pilot:
            await body(app, pilot)

    asyncio.run(go())


def header(app: MapApp) -> str:
    return str(app.query_one("#header", Static).content)


def visible_rows(app: MapApp) -> list[str]:
    view = app.query_one(MapView)
    return [view.row_text(y) for y in range(view.size.height)]


def test_header_names_seed_level_and_glyphs() -> None:
    async def body(app: MapApp, pilot: object) -> None:
        text = header(app)
        assert "1:BRASSLAMP42" in text and "Level 1" in text and "unicode" in text

    drive((100, 30), body)


def test_map_opens_centered_so_the_entry_stairs_are_visible() -> None:
    async def body(app: MapApp, pilot: object) -> None:
        assert any("▲" in row for row in visible_rows(app))

    drive((60, 20), body)


def test_arrow_keys_pan_the_camera_and_clamp_at_the_edges() -> None:
    async def body(app: MapApp, pilot) -> None:  # type: ignore[no-untyped-def]
        view = app.query_one(MapView)
        view.cam_x = view.cam_y = 0
        await pilot.press("right")
        assert (view.cam_x, view.cam_y) == (4, 0)
        await pilot.press("left", "left")
        assert view.cam_x == 0
        await pilot.press("down")
        assert view.cam_y == 2
        for _ in range(60):
            await pilot.press("down", "right")
        assert view.cam_x == 80 - view.size.width and view.cam_y == 40 - view.size.height

    drive((60, 20), body)


def test_f2_switches_glyph_set() -> None:
    async def body(app: MapApp, pilot) -> None:  # type: ignore[no-untyped-def]
        assert any("▲" in row for row in visible_rows(app))
        await pilot.press("f2")
        assert app.glyph_name == "ascii"
        rows = visible_rows(app)
        assert any("<" in row for row in rows) and not any("▲" in row for row in rows)
        await pilot.press("f2")
        assert app.glyph_name == "unicode"

    drive((60, 20), body)


def test_brackets_change_level_within_one_to_five() -> None:
    async def body(app: MapApp, pilot) -> None:  # type: ignore[no-untyped-def]
        await pilot.press("left_square_bracket")
        assert app.level == 1
        await pilot.press("right_square_bracket")
        assert app.level == 2
        assert "Level 2" in header(app)
        for _ in range(6):
            await pilot.press("right_square_bracket")
        assert app.level == 5

    drive((100, 30), body)


def test_q_quits() -> None:
    async def body(app: MapApp, pilot) -> None:  # type: ignore[no-untyped-def]
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running

    drive((100, 30), body)
