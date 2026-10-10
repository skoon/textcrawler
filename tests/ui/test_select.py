"""The class select screen shown before a new run."""

import asyncio

from textual.pilot import Pilot
from textual.widgets import Static

from minetoofar.ui.select import ClassSelectApp


def pick(keys: list[str]) -> str | None:
    async def go() -> str | None:
        app = ClassSelectApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            for key in keys:
                await pilot.press(key)
        return app.return_value

    return asyncio.run(go())


def shown(body: object) -> str:
    async def go() -> str:
        app = ClassSelectApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            return await body(app, pilot)  # type: ignore[operator, no-any-return]

    return asyncio.run(go())


def test_the_first_class_is_selected_and_enter_signs() -> None:
    assert pick(["enter"]) == "fighter"


def test_digits_choose_a_class_directly() -> None:
    assert pick(["2", "enter"]) == "rogue"
    assert pick(["3", "enter"]) == "ranger"
    assert pick(["3", "1", "enter"]) == "fighter"


def test_arrows_and_vi_keys_move_the_choice_and_stop_at_the_ends() -> None:
    assert pick(["down", "down", "enter"]) == "ranger"
    assert pick(["down", "down", "down", "enter"]) == "ranger"
    assert pick(["j", "k", "k", "enter"]) == "fighter"
    assert pick(["down", "up", "enter"]) == "fighter"


def test_q_or_escape_quits_without_choosing() -> None:
    assert pick(["q"]) is None
    assert pick(["escape"]) is None


def test_the_screen_shows_each_class_with_its_numbers_and_blurb() -> None:
    async def body(app: ClassSelectApp, pilot: Pilot[None]) -> str:
        return str(app.query_one("#select", Static).render())

    out = shown(body)
    assert asyncio.run(_title()) == "CHOOSE YOUR CLASSIFICATION"
    for needle in (
        "Fighter",
        "Rogue",
        "Ranger",
        "HP 30",
        "HP 22",
        "HP 26",
        "STR 16",
        "DEX 16",
        "Company Pickaxe",
        "Box Cutter",
        "Hatchet",
        "Refuses to fall down",
        "[Enter]",
    ):
        assert needle in out, needle


def test_the_selected_class_is_marked() -> None:
    async def body(app: ClassSelectApp, pilot: Pilot[None]) -> str:
        await pilot.press("2")
        return str(app.query_one("#select", Static).render())

    marked = [line for line in shown(body).splitlines() if line.startswith(">")]
    assert len(marked) == 1 and "Rogue" in marked[0]


async def _title() -> str:
    app = ClassSelectApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        return app.query_one("#select", Static).border_title or ""
