"""Finishing a level on screen: the pay slip, the next level, death, and the performance review."""

from textual.pilot import Pilot

from minetoofar.core.seed import Seed
from minetoofar.sim.economy import Account
from minetoofar.sim.events import Wait
from minetoofar.sim.game import Game
from minetoofar.sim.ledger import Salvage
from minetoofar.ui.game_app import DeathScreen, GameApp, ReviewScreen, SlipScreen
from minetoofar.ui.mapview import MapView
from tests.helpers import BALANCE, make_game
from tests.ui.test_game_app import run_app, text
from tests.ui.test_game_fight import doomed_game

BASE = BALANCE.economy.base_fee  # the Base Job Fee as shipped

SEED = Seed.parse("GOLD0012")  # no graveyard floors, so no Hazard Premium
ROOM = ["#" * 12, "#<.........#", "#" * 12]


def on(game: Game, body: object) -> None:
    run_app(GameApp(game, "unicode"), (80, 40), body)  # type: ignore[arg-type]


def at_exit(level: int = 1) -> Game:
    game = Game.new(SEED, level)
    game.player.pos = game.spec.exit
    return game


def slip_text(app: GameApp) -> str:
    return str(app.screen.query_one("#slip").render())


async def open_slip(pilot: Pilot[None]) -> None:
    """Take the Down Shaft and get past the field report to the pay slip."""
    await pilot.press("greater_than_sign", "enter")


def test_descending_opens_the_slip_and_signing_it_starts_the_next_level_with_the_purse() -> None:
    game = at_exit()
    game.ledger.salvage.append(Salvage("rough_gem", "Rough Gem", 4, 2))

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await open_slip(pilot)
        assert isinstance(app.screen, SlipScreen)
        shown = slip_text(app)
        assert "Base Job Fee" in shown and "Salvage Credit: Rough Gem x2 @4g" in shown
        assert "NET PAY" in shown and f"+{BASE + 8}g" in shown
        assert app.screen.query_one("#slipbox").border_title == app.text.line("slip_title")
        await pilot.press("enter", "enter", "enter")  # sign; the memo; the desk
        await pilot.pause()
        assert not isinstance(app.screen, SlipScreen)
        assert app.game.spec.level == 2 and app.game.account.wallet == BASE + 8
        assert f"Gold {BASE + 8}g" in text(app, "#status")
        assert "Work Order 2 of 5" in app.messages[-1]
        assert app.query_one(MapView).border_title.endswith("L2")

    on(game, body)


def test_descending_away_from_the_shaft_is_still_refused() -> None:
    game = Game.new(SEED, 1)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("greater_than_sign")
        assert not isinstance(app.screen, SlipScreen)
        assert app.messages[-1] == app.text.line("descend_none")

    on(game, body)


def test_the_slip_lines_match_what_was_done_on_the_level() -> None:
    game = at_exit(3)
    game.ledger.traps = 1
    game.player.body_dur = 10

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("enter", "enter")  # the report, then the slip
        shown = slip_text(app)
        assert "Hazard Surcharge" in shown and "Armor repair: Boiler Suit, 8 pts" in shown
        assert "-4g" in shown and "-3g" in shown  # ceil(8 * 2 / 4) and the surcharge

    on(game, body)


def test_r_declines_repair_and_the_damage_goes_with_you() -> None:
    game = at_exit()
    game.player.body_dur = 10

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await open_slip(pilot)
        assert "Armor repair" in slip_text(app)
        await pilot.press("r")
        assert "Armor repair" not in slip_text(app)
        await pilot.press("enter")
        await pilot.pause()
        assert app.game.player.body_dur == 10 and app.game.account.wallet == BASE

    on(game, body)


def test_a_coupon_is_spent_by_pressing_the_number_of_a_line() -> None:
    game = at_exit()
    game.account = Account(coupons=1)
    game.ledger.clock_ins = 5

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await open_slip(pilot)
        assert "[1] Timecard Irregularity x5" in slip_text(app)
        await pilot.press("1")
        assert "waived: Coupon (3g)" in slip_text(app)
        await pilot.press("1")  # again: take it back
        assert "waived: Coupon" not in slip_text(app)
        await pilot.press("1", "enter")
        await pilot.pause()
        assert app.game.account.coupons == 0 and app.game.account.wallet == BASE - 2

    on(game, body)


def test_f5_skips_to_the_next_level_with_the_books_balanced() -> None:
    game = Game.new(SEED, 1)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("f5")
        await pilot.pause()
        assert not isinstance(app.screen, SlipScreen)
        assert app.game.spec.level == 2 and app.game.account.wallet == BASE

    on(game, body)


def test_the_last_level_has_nowhere_to_go_but_the_review() -> None:
    game = at_exit(5)
    game.ledger.bounty = True

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("f5")
        assert app.messages[-1] == app.text.line("descend_last")
        await open_slip(pilot)
        assert isinstance(app.screen, SlipScreen)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ReviewScreen)
        shown = str(app.screen.query_one("#death").render())
        assert app.text.line("review_surface") in shown
        assert (
            app.text.line("death_score", score=BASE + 6 + 10 + 5) in shown
        )  # wallet, a level, a bounty
        assert app.text.line("death_final_title", title=app.text.line("title_valued")) in shown
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running

    on(game, body)


async def to_the_slip(app: GameApp, pilot: Pilot[None]) -> None:
    for _ in range(60):
        if isinstance(app.screen, SlipScreen):
            return
        await pilot.press("full_stop")
        await pilot.pause()
    raise AssertionError("the Fighter never died")


def test_death_prints_the_posthumous_slip_and_then_the_report_with_score_and_title() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await to_the_slip(app, pilot)
        assert app.game.dead
        assert app.screen.query_one("#slipbox").border_title == app.text.line(
            "slip_posthumous_title"
        )
        assert "Uniform Recovery Fee" in slip_text(app)
        assert "Base Job Fee" not in slip_text(app)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DeathScreen)
        shown = str(app.screen.query_one("#death").render())
        score = app.game.score()
        assert score <= 0 and app.text.line("death_score", score=score) in shown
        assert app.text.line("death_final_title", title=app.text.line("title_terminated")) in shown

    on(doomed_game(), body)


def test_retrying_after_a_death_puts_the_purse_back_as_it_was_on_arrival() -> None:
    game = Game.new(SEED, 1)
    game.ledger.salvage.append(Salvage("rough_gem", "Rough Gem", 4, 1))

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("f5")
        await pilot.pause()
        arrived = app.game.account
        assert arrived.wallet == BASE + 4
        app.game.player.hp = 0
        app.game.dead = True
        app.game.cause = "a test"
        app._report_death()
        await pilot.pause()
        await pilot.press("enter")  # the posthumous slip
        await pilot.pause()
        assert app.game.account != arrived  # the Uniform Recovery Fee has been charged
        await pilot.press("r")
        await pilot.pause()
        assert app.game.spec.level == 2 and app.game.account == arrived
        assert not app.game.dead and app.game.cleared == 1

    on(game, body)


def test_the_wait_key_still_works_with_a_purse() -> None:
    game = make_game(ROOM, account=Account(wallet=3))

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("full_stop")
        assert app.game.ticks == 100 and Wait() is not None

    on(game, body)
