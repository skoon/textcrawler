"""The check-in (GDD 3, 5.3, 8.5): the field report, promotion, the Wellness Break, Standard
Issue, and the Requisitions Desk."""

import pytest

from minetoofar.core.geometry import Pos
from minetoofar.core.seed import Seed
from minetoofar.gen.desk import generate_desk
from minetoofar.sim.actors import Item
from minetoofar.sim.checkin import Checkin, field_report
from minetoofar.sim.economy import Account
from minetoofar.sim.game import Game
from minetoofar.sim.ledger import Salvage
from tests.helpers import BALANCE, make_game

SEED = Seed.parse("GOLD0012")
HALL = ["#" * 12, "#<.........#", "#" * 12]
CELL = ["####", "#<.#", "####"]


def face(n: int) -> int:
    return n - 1


def done(level: int = 2, account: Account | None = None, rank: int = 1) -> Game:
    """A real level that has just been checked out of with a wallet to spend."""
    g = Game.new(SEED, level, rank=rank)
    g.account = account or Account(wallet=100)
    g.check_out()
    return g


def stock_of(level: int) -> list[str]:
    return list(generate_desk(SEED, level).stock)


# -- the field report ----------------------------------------


def test_the_report_tallies_the_level() -> None:
    g = Game.new(SEED, 2)
    g.ledger.undead_kills, g.ledger.beast_kills = 5, 7
    g.ledger.salvage += [
        Salvage("silver_nugget", "Silver Nugget", 2, 2),
        Salvage("rough_gem", "Rough Gem", 4, 1),
    ]
    g.player.pos = Pos(1, 1)
    g.player.ready_at = 61250
    r = field_report(g)
    assert (r.level, r.undead, r.beasts, r.valuables, r.turns) == (2, 5, 7, 3, 612)


def test_the_unauthorized_person_is_at_large_or_retrieved() -> None:
    g = Game.new(SEED, 1)
    r = field_report(g)
    assert r.human == "Foreman Grimsby" and not r.human_down
    g.ledger.bounty = True
    assert field_report(g).human_down


def test_the_report_says_what_standard_issue_will_top_up() -> None:
    g = Game.new(SEED, 1)
    assert field_report(g).issued == ()
    g.player.pack[:] = [Item("patch_up_kit", 1, 0)]
    assert field_report(g).issued == (("Patch-Up Kit", 1), ("Torch", 1))


def test_the_report_announces_a_promotion_and_the_ability_it_unlocks() -> None:
    r = field_report(Game.new(SEED, 2))  # after Level 2 comes Rank 3
    assert (r.promoted_to, r.unlocked) == (3, "Cleave")
    r = field_report(Game.new(SEED, 1))  # Rank 2: stronger, nothing new
    assert (r.promoted_to, r.unlocked) == (2, "")


def test_a_higher_starting_rank_is_never_demoted() -> None:
    assert field_report(Game.new(SEED, 1, rank=5)).promoted_to == 0
    assert field_report(Game.new(SEED, 3, rank=2)).promoted_to == 4


# -- promotion and the Wellness Break -----------------------------------------------------


@pytest.mark.parametrize(("level", "rank"), [(1, 2), (2, 3), (3, 4), (4, 5)])
def test_each_check_in_promotes_one_rank(level: int, rank: int) -> None:
    c = Checkin(done(level))
    carry = c.finish()
    assert carry.player.rank == rank
    assert carry.player.hp == carry.player.max_hp  # the Wellness Break: free


def test_promotion_raises_the_numbers_on_the_sheet() -> None:
    carry = Checkin(done(1)).finish()
    nxt = Game.new(SEED, 2, carry=carry)
    assert (nxt.player.rank, nxt.player.max_hp) == (2, 35)
    assert nxt.view().hero.atk == 6  # +1 ATK at Rank 2


def test_there_is_no_check_in_after_the_last_level_or_for_the_dead() -> None:
    with pytest.raises(ValueError, match="last level"):
        Checkin(done(5))
    g = make_game(CELL, level=1)
    g.dead = True
    with pytest.raises(ValueError, match="dead"):
        Checkin(g)


# -- the desk ----------------------------------------


def test_the_desk_stocks_what_the_seed_says() -> None:
    c = Checkin(done(1))
    assert c.stock == stock_of(1) and c.memo == generate_desk(SEED, 1).memo
    assert c.open and len(c.stock) == 4


def test_an_account_in_debt_finds_the_desk_closed() -> None:
    c = Checkin(done(1, Account(wallet=0, debt=40)))
    assert not c.open
    assert c.buy(0).reason == "on_hold" and c.account.debt > 0


def test_buying_pays_from_the_wallet_and_each_slot_sells_once() -> None:
    c = Checkin(done(1, Account(wallet=100)))
    start = c.account.wallet
    bought = c.buy(0)
    assert bought.ok and c.account.wallet == start - c.price(0)
    assert c.buy(0).reason == "sold" and c.account.wallet == start - c.price(0)


def test_a_wallet_too_light_buys_nothing() -> None:
    c = Checkin(done(1, Account(wallet=0)))
    c.account = Account(wallet=1)
    before = c.player.pack[:]
    assert c.buy(0).reason == "poor" and c.account.wallet == 1 and c.player.pack == before


def test_a_bad_slot_is_refused() -> None:
    c = Checkin(done(1))
    with pytest.raises(IndexError):
        c.buy(9)


def force(c: Checkin, key: str) -> int:
    """Put `key` into slot 0 and return that slot."""
    c.stock[0] = key
    return 0


def test_a_torch_bundle_is_three_prepaid_torches_if_they_fit() -> None:
    c = Checkin(done(1))
    c.player.pack[:] = []
    assert c.buy(force(c, "torch_bundle")).ok
    assert c.player.pack == [Item("torch", 3, 0)]


def test_a_bundle_that_will_not_fit_is_refused_and_costs_nothing() -> None:
    c = Checkin(done(1))
    c.player.pack[:] = [Item("torch", 2, 2)]
    wallet = c.account.wallet
    assert c.buy(force(c, "torch_bundle")).reason == "no_room"
    assert c.account.wallet == wallet and c.sold == set()


def test_a_kit_bundle_is_two_prepaid_kits() -> None:
    c = Checkin(done(1))
    c.player.pack[:] = []
    assert c.buy(force(c, "kit_bundle")).ok and c.player.pack == [Item("patch_up_kit", 2, 0)]


def test_sharpening_adds_damage_up_to_three_and_hone_adds_attack_up_to_two() -> None:
    c = Checkin(done(1, Account(wallet=500)))
    for _ in range(3):
        c.sold.clear()
        assert c.buy(force(c, "sharpening_service")).ok
    c.sold.clear()
    assert c.buy(force(c, "sharpening_service")).reason == "capped"
    for _ in range(2):
        c.sold.clear()
        assert c.buy(force(c, "hone_and_balance")).ok
    c.sold.clear()
    assert c.buy(force(c, "hone_and_balance")).reason == "capped"
    assert c.player.weapon_mods == {"company_pickaxe": (3, 2)}


def test_the_edge_goes_on_the_weapon_in_hand_and_shows_next_level() -> None:
    c = Checkin(done(1))
    c.buy(force(c, "sharpening_service"))
    nxt = Game.new(SEED, 2, carry=c.finish())
    assert nxt.view().hero.damage == "1d8+4"  # +3 STR, +1 sharpened


def test_armor_plating_once_per_armor() -> None:
    c = Checkin(done(1, Account(wallet=500)))
    worn = c.player.body_dur
    assert c.buy(force(c, "armor_plating")).ok
    assert c.player.plated == {"boiler_suit"} and c.player.body_dur == worn + 4
    c.sold.clear()
    assert c.buy(force(c, "armor_plating")).reason == "have_it"


def test_a_reinforced_hard_hat_goes_in_the_pack() -> None:
    c = Checkin(done(1))
    assert c.buy(force(c, "reinforced_hard_hat")).ok
    assert Item("reinforced_hard_hat") in c.player.pack


def test_a_wellness_seminar_is_three_hit_points_for_good() -> None:
    c = Checkin(done(1))
    assert c.buy(force(c, "wellness_seminar")).ok
    carry = c.finish()
    assert carry.player.hp_bonus == 3
    nxt = Game.new(SEED, 2, carry=carry)
    assert nxt.player.max_hp == 35 + 3 and nxt.player.hp == nxt.player.max_hp


@pytest.mark.parametrize(
    ("key", "flag"),
    [("repair_plan", "repair_plan"), ("property_damage_waiver", "damage_waiver"),
     ("hazard_waiver", "hazard_waiver")],
)  # fmt: skip
def test_the_slips_waivers_are_bought_once_and_kept_for_the_next_slip(key: str, flag: str) -> None:
    c = Checkin(done(1))
    assert c.buy(force(c, key)).ok
    assert getattr(c.account, flag) is True
    c.sold.clear()
    assert c.buy(force(c, key)).reason == "have_it"
    assert getattr(Game.new(SEED, 2, carry=c.finish()).account, flag) is True


def test_finishing_carries_the_purchases_and_the_purse_to_the_next_level() -> None:
    g = done(1, Account(wallet=50))
    c = Checkin(g)
    c.buy(force(c, "kit_bundle"))
    carry = c.finish()
    assert carry.account.wallet == 50 + BALANCE.economy.base_fee - 8 and carry.cleared == 1
    nxt = Game.new(SEED, 2, carry=carry)
    assert nxt.account.wallet == carry.account.wallet and nxt.cleared == 1


def test_a_check_in_does_not_touch_the_game_it_came_from() -> None:
    g = done(1)
    before = g.state_hash()
    c = Checkin(g)
    c.buy(force(c, "wellness_seminar"))
    assert g.state_hash() == before
