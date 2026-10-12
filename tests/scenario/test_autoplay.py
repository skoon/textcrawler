"""The scripted run-player behind the balance simulator (GDD 8.6) and the full-run tests."""

from minetoofar.core.seed import Seed
from minetoofar.sim.autoplay import _shop
from minetoofar.sim.checkin import Checkin
from minetoofar.sim.economy import Account
from minetoofar.sim.game import Game

SEED = Seed.parse("GOLD0012")


def desk(wallet: int) -> Checkin:
    g = Game.new(SEED, 2)
    g.account = Account(wallet=wallet)
    g.check_out()
    return Checkin(g)


def test_shopping_without_a_reserve_spends_what_it_can() -> None:
    ci = desk(100)
    before = ci.account.wallet
    assert _shop(ci, tuple(ci.stock), reserve=0) and ci.account.wallet < before


def test_shopping_leaves_the_reserve_in_the_wallet() -> None:
    ci = desk(100)
    reserve = ci.account.wallet - 5
    _shop(ci, tuple(ci.stock), reserve=reserve)
    assert ci.account.wallet >= reserve


def test_a_reserve_bigger_than_the_wallet_buys_nothing() -> None:
    ci = desk(30)
    before = ci.account.wallet
    assert _shop(ci, tuple(ci.stock), reserve=before + 1) == []
    assert ci.account.wallet == before
