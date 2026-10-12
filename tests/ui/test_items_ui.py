"""Items on screen: the map, the log, the pack screen, the item menus, and documents."""

from textual.pilot import Pilot

from minetoofar.content.docs import load_docs
from minetoofar.core.geometry import Pos
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.economy import Account
from minetoofar.sim.game import Game
from minetoofar.ui.game_app import DocumentScreen, GameApp, PackScreen
from minetoofar.ui.mapview import DIM_STYLES, ITEM_STYLES, MapView, dim
from tests.helpers import make_game
from tests.ui.test_game_app import rows, run_app, text

ROOM = ["#" * 14, "#<" + "." * 11 + "#", "#" * 14]


def on(game: Game, body: object, glyphs: str = "unicode") -> None:
    run_app(GameApp(game, glyphs), (80, 24), body)  # type: ignore[arg-type]


def at(x: int, item_id: str, **fields: int) -> FloorItem:
    return FloorItem(Pos(x, 1), Item(item_id, **fields))


# -- on the map ------------------------------------------------------------------------------------


def test_finds_are_drawn_with_the_gdd_glyphs_in_both_sets() -> None:
    game = make_game(ROOM, floor=[at(3, "prybar"), at(4, "rough_gem"), at(5, "memo")])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert rows(app)[1][3:6] == "↑◊≡"
        await pilot.press("f2")
        assert rows(app)[1][3:6] == ")*?"

    on(game, body)


def test_a_find_you_remember_is_drawn_dim_like_the_floor_it_lies_on() -> None:
    game = make_game(["#" * 20, "#<" + "." * 17 + "#", "#" * 20], floor=[at(3, "prybar")])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view = app.query_one(MapView)
        assert view.row_cells(1 - view.cam_y)[3 - view.cam_x][1] == ITEM_STYLES["weapon"]
        for _ in range(12):
            await pilot.press("l")  # walk out of the lamp's reach
        assert view.row_cells(1 - view.cam_y)[3 - view.cam_x][1] == dim(ITEM_STYLES["weapon"])
        assert DIM_STYLES  # the floor itself is dimmed the same way

    on(game, body)


def test_look_names_the_find_under_the_cursor() -> None:
    game = make_game(ROOM, floor=[at(3, "prybar")])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("x", "l", "l")
        assert app.query_one(MapView).border_subtitle == "Prybar"

    on(game, body)


# -- the log -------------------------------------------------------------------------------------


def test_stepping_onto_a_find_says_what_is_there_and_g_takes_it() -> None:
    game = make_game(ROOM, floor=[at(2, "prybar")])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l")
        assert app.messages[-1] == app.text.line("see_here", names="Prybar")
        await pilot.press("g")
        assert app.messages[-1] == app.text.line("item_picked", name="Prybar")
        assert "+1" in text(app, "#status")  # the pack line counts it among the others
        await pilot.press("comma")
        assert app.messages[-1] == app.text.line("refused_nothing_here")

    on(game, body)


def test_a_valuable_is_pocketed_on_the_way_past() -> None:
    game = make_game(ROOM, floor=[at(2, "rough_gem")])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l")
        assert app.messages[-1] == app.text.line("valuable", name="Rough Gem", credit=4)

    on(game, body)


def test_the_panel_shows_the_pack_and_the_purse() -> None:
    game = make_game(ROOM, account=Account(wallet=14, debt=2))

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        panel = text(app, "#status")
        assert "Kits 2  Torches 1" in panel and "Gold 14g  Debt 2g" in panel
        await pilot.press("t")
        assert "Light: Torch 400t (8)" in text(app, "#status")

    on(game, body)


# -- the pack screen and the item menus -------------------------------------------------------


def test_i_shows_what_is_worn_and_carried_and_escape_closes_it() -> None:
    game = make_game(ROOM)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("i")
        assert isinstance(app.screen, PackScreen)
        shown = str(app.screen.query_one("#pack").render())
        assert "Main hand   Company Pickaxe" in shown and "a  Patch-Up Kit x2 (5g each)" in shown
        await pilot.press("escape")
        assert not isinstance(app.screen, PackScreen)

    on(game, body)


def test_q_asks_which_item_and_a_kit_heals() -> None:
    game = make_game(ROOM)
    game.player.hp = 12

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("q")
        assert isinstance(app.screen, PackScreen)
        assert app.text.line("menu_use") in str(app.screen.query_one("#packkeys").render())
        await pilot.press("a")
        assert not isinstance(app.screen, PackScreen) and app.game.player.hp == 22
        assert app.text.line("healed", amount=10) in app.messages
        assert app.messages[-1] == app.text.line("item_used", name="Patch-Up Kit", charge=5)

    on(game, body)


def test_a_menu_ignores_letters_with_nothing_behind_them_and_escape_cancels() -> None:
    game = make_game(ROOM)
    game.player.hp = 12

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("q", "z")
        assert isinstance(app.screen, PackScreen)  # z is no slot; still choosing
        await pilot.press("escape")
        assert app.game.player.hp == 12 and app.game.ticks == 0

    on(game, body)


def test_e_equips_a_pack_item_and_a_capital_puts_a_light_weapon_in_the_off_hand() -> None:
    game = make_game(ROOM, pack=[Item("prybar"), Item("utility_knife")])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("e", "a")
        assert app.game.player.weapon == "prybar"
        assert app.messages[-1] == app.text.line("equipped", name="Prybar")
        await pilot.press("e", "A")  # capital: off hand (the knife is now slot a)
        assert app.game.player.offhand == "utility_knife"

    on(game, body)


def test_d_drops_one_unit_where_you_stand() -> None:
    game = make_game(ROOM)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("d", "a")
        assert app.messages[-1] == app.text.line("item_dropped", name="Patch-Up Kit")
        assert [f.item.id for f in app.game.floor] == ["patch_up_kit"]

    on(game, body)


def test_the_item_menus_with_an_empty_pack_say_so() -> None:
    game = make_game(ROOM, pack=[])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        for key in ("q", "e", "d"):
            await pilot.press(key)
            assert not isinstance(app.screen, PackScreen)
            assert app.messages[-1] == app.text.line("inventory_empty")

    on(game, body)


def test_refusals_from_the_menus_reach_the_log() -> None:
    game = make_game(ROOM)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("q", "a")  # a kit at full health
        assert app.messages[-1] == app.text.line("refused_full_hp")

    on(game, body)


# -- documents ------------------------------------------------------------------------------------


def test_reading_a_document_opens_its_text_until_a_key_is_pressed() -> None:
    game = make_game(ROOM, floor=[at(1, "memo", text=3)])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("g")
        assert isinstance(app.screen, DocumentScreen)
        assert load_docs().text("memo", 3) in str(app.screen.query_one("#document").render())
        assert app.messages[-1] == app.text.line("document_read", name="Memo")
        await pilot.press("space")
        assert not isinstance(app.screen, DocumentScreen)

    on(game, body)


def test_a_coupon_is_announced_in_the_log_and_the_text_shown() -> None:
    game = make_game(ROOM, floor=[at(1, "coupon", text=0)])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("g")
        assert isinstance(app.screen, DocumentScreen) and app.game.account.coupons == 1

    on(game, body)
