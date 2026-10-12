"""Finishing a level: the pay slip matches what happened, armor is repaired, and the Associate
carries pack, kit and account to the next level (GDD 3, 8.6, 8.8)."""

from minetoofar.core.geometry import Pos
from minetoofar.core.seed import Seed
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.economy import Account, Choices
from minetoofar.sim.events import (
    DropItem,
    Equip,
    Move,
    Pickup,
    UseItem,
    Wait,
)
from minetoofar.sim.game import Game, GameOver
from minetoofar.sim.traps import Trap
from tests.helpers import BALANCE, MINER, ScriptedRng, make_game

E = Move(1, 0)
BASE = BALANCE.economy.base_fee  # the Base Job Fee as shipped
HALL = ["#" * 12, "#<.........#", "#" * 12]
CELL = ["####", "#<.#", "####"]


def face(n: int) -> int:
    return n - 1


def owed(slip_lines: tuple[object, ...]) -> dict[str, int]:
    return {line.key: line.owed for line in slip_lines}  # type: ignore[attr-defined]


# -- check-out ------------------------------------------------------------------------------


def test_checking_out_pays_the_wallet_and_counts_the_level() -> None:
    g = make_game(HALL)
    s = g.check_out()
    assert (s.net, g.account.wallet, g.account.debt) == (BASE, BASE, 0)
    assert g.cleared == 1 and g.bounties == 0


def test_a_bounty_is_counted_when_the_human_fell() -> None:
    g = make_game(HALL)
    g.ledger.bounty = True
    s = g.check_out()
    assert s.gross == BASE + 6 and g.bounties == 1


def test_repair_is_billed_and_the_armor_is_made_good() -> None:
    g = make_game(HALL)
    g.player.body_dur = 10
    s = g.check_out()
    assert owed(s.adjustments) == {"repair": 4} and g.player.body_dur == 18  # ceil(8 * 2 / 4)


def test_declining_repair_keeps_the_gold_and_the_damage() -> None:
    g = make_game(HALL)
    g.player.body_dur = 10
    s = g.check_out(Choices(repair=False))
    assert owed(s.adjustments) == {} and g.player.body_dur == 10


def test_previewing_the_slip_changes_nothing() -> None:
    g = make_game(HALL)
    g.player.body_dur = 10
    before = g.state_hash()
    g.slip()
    g.slip(Choices(repair=False))
    assert g.state_hash() == before and g.account == Account() and g.cleared == 0


def test_the_pack_is_topped_up_to_standard_issue_after_the_slip() -> None:
    g = make_game(HALL, pack=[Item("patch_up_kit", 1, 3)])
    g.check_out()
    assert g.player.pack == [
        Item("patch_up_kit", 1, 3),
        Item("patch_up_kit", 1, 5),
        Item("torch", 1, 2),
    ]


def test_a_laminated_lanyard_waives_the_first_small_incident() -> None:
    g = make_game(HALL, pack=[Item("laminated_lanyard")])
    g.submit(Equip(0))
    g.ledger.clock_ins = 2
    assert owed(g.slip().adjustments) == {"timecard": 0}
    g.player.trinket = ""
    assert owed(g.slip().adjustments) == {"timecard": 2}


def test_waivers_bought_earlier_apply_and_are_used_up() -> None:
    g = make_game(HALL, account=Account(wallet=5, hazard_waiver=True, damage_waiver=True))
    g.ledger.traps, g.ledger.tripwires, g.ledger.torches_dropped = 1, 1, 1
    s = g.check_out()
    assert s.adjusted == 0 and g.account.hazard_waiver is False and g.account.damage_waiver is False


def test_coupons_are_spent_on_the_chosen_lines() -> None:
    g = make_game(HALL, account=Account(coupons=2))
    g.ledger.clock_ins = 5
    s = g.check_out(Choices(coupons=("timecard",)))
    assert owed(s.adjustments) == {"timecard": 2} and g.account.coupons == 1


def test_debt_carries_to_the_next_slip_with_a_late_fee() -> None:
    g = make_game(HALL, pack=[Item("patch_up_kit", 4, 5)])
    g.player.hp = 1
    for _ in range(4):
        g.player.hp = 1
        g.submit(UseItem(0))  # 20g of kits against the Base Job Fee
    g.check_out()
    assert (g.account.wallet, g.account.debt) == (0, 20 - BASE)
    g2 = make_game(HALL, account=g.account)
    assert owed(g2.slip().adjustments) == {"carried": 20 - BASE, "late_fee": 1}


# -- death --------------------------------------------------------------------------------------


def test_a_death_prints_the_posthumous_slip_and_clears_no_level() -> None:
    g = make_game(CELL, [(MINER, (2, 1), "hunting")], ScriptedRng([face(20), face(6), face(6)]))
    g.player.hp = 1
    g.player.stubborn_used = True
    g.submit(Wait())
    assert g.dead
    s = g.check_out()
    assert s.posthumous and "base" not in owed(s.gross_lines)
    assert owed(s.adjustments)["uniform"] == 5
    assert g.cleared == 0 and g.account.debt > 0


def test_commands_after_death_still_raise() -> None:
    g = make_game(CELL, [(MINER, (2, 1), "hunting")], ScriptedRng([face(20), face(6), face(6)]))
    g.player.hp, g.player.stubborn_used = 1, True
    g.submit(Wait())
    g.check_out()
    try:
        g.submit(Wait())
    except GameOver:
        return
    raise AssertionError("a dead Associate must not act")


# -- score ----------------------------------------------------------------------------------------


def test_the_score_counts_wealth_levels_and_bounties() -> None:
    g = make_game(HALL)
    g.ledger.bounty = True
    g.check_out()
    assert g.score() == BASE + 6 + 10 + 5  # wallet, one level, one bounty


# -- carrying on to the next level ------------------------------------------------------------


def test_the_next_level_starts_with_the_same_kit_pack_and_purse() -> None:
    seed = Seed.parse("GOLD0001")
    g = Game.new(seed, 1)
    g.player.pack.append(Item("welders_jacket", 1, 0, 9))
    g.player.weapon = "prybar"
    g.player.trinket = "company_challenge_coin"
    g.player.body_dur = 5
    g.player.torch_left = 12345
    g.player.hp = 3
    g.player.stubborn_used = True
    g.ledger.salvage.clear()
    g.check_out()
    nxt = Game.new(seed, 2, carry=g.carry_over())
    assert nxt.spec.level == 2 and nxt.ledger.level == 2 and nxt.ledger.salvage == []
    p = nxt.player
    assert (p.weapon, p.trinket, p.body_dur, p.torch_left) == (
        "prybar",
        "company_challenge_coin",
        18,
        12345,
    )
    assert Item("welders_jacket", 1, 0, 9) in p.pack and p.hp == p.max_hp
    assert not p.stubborn_used and p.pos == nxt.spec.entry and nxt.ticks == 0
    assert nxt.account.wallet == g.account.wallet and nxt.cleared == 1


def test_carrying_on_copies_the_pack_so_levels_cannot_share_stacks() -> None:
    seed = Seed.parse("GOLD0001")
    g = Game.new(seed, 1)
    g.check_out()
    carry = g.carry_over()
    nxt = Game.new(seed, 2, carry=carry)
    nxt.player.pack[0].qty = 99
    assert carry.player.pack[0].qty != 99


def test_the_state_hash_notices_the_pack_the_floor_and_the_purse() -> None:
    base = make_game(HALL).state_hash()
    g = make_game(HALL)
    g.player.pack.append(Item("hatchet"))
    assert g.state_hash() != base
    g = make_game(HALL, floor=[FloorItem(Pos(3, 1), Item("prybar"))])
    assert g.state_hash() != base
    g = make_game(HALL, account=Account(wallet=1))
    assert g.state_hash() != base
    g = make_game(HALL)
    g.player.torch_left = 5
    assert g.state_hash() != base
    g = make_game(HALL)
    g.submit(DropItem(0))
    assert g.state_hash() != base
    g = make_game(HALL)
    g.ledger.traps = 1
    assert g.state_hash() != base


def test_a_trap_sprung_shows_up_on_the_slip() -> None:
    g = make_game(HALL, traps=[Trap(Pos(2, 1), "spring_trap")], rng=ScriptedRng([face(3)]))
    g.submit(E)
    assert owed(g.slip().adjustments) == {"hazard_surcharge": 3}


def test_picking_up_and_using_found_stock_bills_half_price() -> None:
    g = make_game(HALL, floor=[FloorItem(Pos(1, 1), Item("patch_up_kit", 1, 3))], pack=[])
    g.player.hp = 1
    g.submit(Pickup())
    g.submit(UseItem(0))
    assert owed(g.slip().adjustments) == {"used:patch_up_kit:3": 3}


def test_the_turns_of_every_level_add_up_across_a_run() -> None:
    seed = Seed.parse("GOLD0001")
    g = Game.new(seed, 1)
    g.player.ready_at = 12345  # 123 turns
    g.check_out()
    nxt = Game.new(seed, 2, carry=g.carry_over())
    assert nxt.total_turns == 123
    nxt.player.ready_at = 700
    assert nxt.total_turns == 130 and nxt.carry_over().turns == 130
