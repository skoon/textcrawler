"""The check-in on screen (GDD 5.3) and the supply crate (GDD 8.5), end to end."""

from textual.pilot import Pilot

from minetoofar.core.geometry import Pos
from minetoofar.core.seed import Seed
from minetoofar.gen.desk import generate_desk
from minetoofar.gen.drops import SupplyDrop, SupplyLine
from minetoofar.sim.actors import Item
from minetoofar.sim.economy import Account
from minetoofar.sim.game import Game
from minetoofar.ui.game_app import (
    DeskScreen,
    GameApp,
    InvoiceScreen,
    MemoScreen,
    ReportScreen,
    ReviewScreen,
    SlipScreen,
)
from minetoofar.ui.mapview import MapView
from tests.helpers import BALANCE, make_game
from tests.ui.test_game_app import rows, run_app

BASE = BALANCE.economy.base_fee  # the Base Job Fee as shipped

SEED = Seed.parse("GOLD0012")  # no graveyard floors, so no Hazard Premium
ROOM = ["#########", "#.......#", "#.......#", "#.......#", "#...<...#", "#.......#", "#########"]


def on(game: Game, body: object, size: tuple[int, int] = (80, 40)) -> None:
    run_app(GameApp(game, "unicode"), size, body)  # type: ignore[arg-type]


def at_exit(level: int = 1, account: Account | None = None) -> Game:
    game = Game.new(SEED, level)
    game.player.pos = game.spec.exit
    if account is not None:
        game.account = account
    return game


def shown(app: GameApp, ident: str) -> str:
    return str(app.screen.query_one(ident).render())


def titled(app: GameApp, ident: str) -> str:
    return str(app.screen.query_one(ident).border_title)


# -- the whole check-in ---------------------------------------------------------------


def test_the_report_slip_memo_and_desk_lead_to_the_next_level() -> None:
    desk = generate_desk(SEED, 1)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign")
        assert isinstance(app.screen, ReportScreen)
        assert "CHECK-IN 1 OF 5" in titled(app, "#report")
        assert "Promotion: Rank 2" in shown(app, "#report")
        await pilot.press("enter")
        assert isinstance(app.screen, SlipScreen)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, MemoScreen)
        assert desk.memo is not None and desk.memo.subject in shown(app, "#memo")
        await pilot.press("enter")
        assert isinstance(app.screen, DeskScreen)
        assert "REQUISITIONS DESK" in titled(app, "#desk")
        assert f"Wallet {BASE}g" in titled(app, "#desk")
        await pilot.press("1")
        assert app.screen.checkin.sold == {0}  # type: ignore[attr-defined]
        price = app.screen.checkin.price(0)  # type: ignore[attr-defined]
        assert f"Wallet {BASE - price}g" in titled(app, "#desk")
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, DeskScreen)
        g = app.game
        assert g.spec.level == 2 and g.player.rank == 2 and g.player.hp == g.player.max_hp
        assert g.account.wallet == BASE - price and g.cleared == 1
        assert app.query_one(MapView).border_title.endswith("L2")

    on(at_exit(), body)


def test_the_desk_sells_what_the_seed_stocked_in_slot_order() -> None:
    desk = generate_desk(SEED, 1)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign", "enter", "enter", "enter")
        await pilot.pause()
        assert isinstance(app.screen, DeskScreen)
        shown_desk = shown(app, "#desk")
        for i, key in enumerate(desk.stock, 1):
            assert f"[{i}] {app.screen.checkin.catalog[key].name}" in shown_desk  # type: ignore[attr-defined]

    on(at_exit(), body)


def test_escape_on_the_report_signs_the_defaults_and_goes_to_the_memo() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign", "escape")
        await pilot.pause()
        assert isinstance(app.screen, MemoScreen)
        assert app.game.account.wallet == BASE  # the slip was signed as it stood

    on(at_exit(), body)


def test_a_desk_closed_for_debt_refuses_every_purchase() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign", "enter", "enter", "enter")
        await pilot.pause()
        assert isinstance(app.screen, DeskScreen) and "Account on hold" in titled(app, "#desk")
        await pilot.press("1")
        assert app.text.line("desk_refused_on_hold") in shown(app, "#desk")
        await pilot.press("enter")
        await pilot.pause()
        assert app.game.spec.level == 2 and app.game.account.debt > 0

    on(at_exit(account=Account(debt=100)), body)


def test_a_refused_purchase_says_why_and_charges_nothing() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign", "enter", "enter", "enter")
        await pilot.pause()
        app.screen.checkin.account = Account(wallet=1)  # type: ignore[attr-defined]
        await pilot.press("2")
        assert app.text.line("desk_refused_poor") in shown(app, "#desk")
        assert app.screen.checkin.account.wallet == 1  # type: ignore[attr-defined]

    on(at_exit(), body)


def test_the_last_level_goes_from_report_to_slip_to_the_review_with_no_desk() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign")
        assert isinstance(app.screen, ReportScreen)
        assert "Wellness Break" not in shown(app, "#report")
        await pilot.press("enter", "enter")
        await pilot.pause()
        assert isinstance(app.screen, ReviewScreen)

    on(at_exit(5), body)


def test_the_debug_skip_promotes_too() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("f5")
        await pilot.pause()
        assert app.game.spec.level == 2 and app.game.player.rank == 2

    on(Game.new(SEED, 1), body)


def test_a_retry_returns_to_the_level_with_the_purchases_made_at_the_desk() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign", "enter", "enter", "enter")
        await pilot.pause()
        app.screen.checkin.stock[0] = "wellness_seminar"  # type: ignore[attr-defined]
        await pilot.press("1", "enter")
        await pilot.pause()
        assert app.game.player.hp_bonus == 3
        app.game.dead = True
        app.game.cause = "a test"
        app._report_death()
        await pilot.pause()
        await pilot.press("enter", "r")
        await pilot.pause()
        assert app.game.spec.level == 2 and app.game.player.hp_bonus == 3

    on(at_exit(account=Account(wallet=50)), body)


# -- supply crates ----------------------------------------------------------------------

KIT = SupplyLine("patch_up_kit", 2, 0)
FIZZ = SupplyLine("overtime_fizz", 1, 0)


def with_crate() -> Game:
    return make_game(ROOM, supply=[SupplyDrop(1, (KIT, FIZZ))])


def test_a_crate_lands_with_a_warning_and_is_drawn_as_a_crate() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("full_stop")
        assert app.messages[-1] == app.text.line("supply_inbound")
        assert "■" in "".join(rows(app))
        await pilot.press("f2")
        assert "=" in "".join(rows(app))

    on(with_crate(), body)


def test_stepping_onto_the_crate_shows_the_invoice_and_accepting_bills_it() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("full_stop")
        crate = app.game.crates[0].pos
        app.game.player.pos = Pos(crate.x + 1, crate.y)
        await pilot.press("h")
        assert isinstance(app.screen, InvoiceScreen)
        assert "SUPPLY DROP INVOICE #1" in titled(app, "#invoice")
        await pilot.press("1")
        assert "[x] 1 Patch-Up Kit x2 @ 5g" in shown(app, "#invoice")
        assert "Subtotal" in shown(app, "#invoice")
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, InvoiceScreen)
        assert Item("patch_up_kit", 2, 0) in app.game.player.pack
        assert app.messages[-1] == app.text.line("supply_taken", number=1, total=14)
        assert [ln.item for ln in app.game.crates[0].lines] == ["overtime_fizz"]

    on(with_crate(), body)


def test_space_and_the_arrow_keys_work_the_invoice_too() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("full_stop")
        app.game.player.pos = app.game.crates[0].pos
        await pilot.press("g")
        assert isinstance(app.screen, InvoiceScreen)
        await pilot.press("down", "space")
        out = shown(app, "#invoice")
        assert "  [ ] 1" in out and "> [x] 2" in out
        await pilot.press("up", "space", "enter")
        await pilot.pause()
        assert app.game.ledger.supply[0][0] == "Supply Drop Invoice #1"
        assert app.game.crates == []  # both lines taken, so the crate is gone

    on(with_crate(), body)


def test_leaving_the_invoice_takes_nothing_and_leaves_the_crate() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("full_stop")
        app.game.player.pos = app.game.crates[0].pos
        await pilot.press("g", "1", "escape")
        assert not isinstance(app.screen, InvoiceScreen)
        assert app.game.ledger.supply == [] and len(app.game.crates[0].lines) == 2

    on(with_crate(), body)


def test_accepting_with_nothing_ticked_just_closes_it() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("full_stop")
        app.game.player.pos = app.game.crates[0].pos
        ticks = app.game.ticks
        await pilot.press("g", "enter")
        assert not isinstance(app.screen, InvoiceScreen)
        assert app.game.ticks == ticks and app.game.ledger.supply == []

    on(with_crate(), body)
