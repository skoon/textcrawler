"""Supply drops (GDD 8.5): a crate lands near you on its turn, and you pay for what you take."""

from minetoofar.core.geometry import Pos
from minetoofar.gen.drops import SupplyDrop, SupplyLine
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.events import (
    AtCrate,
    Move,
    Pickup,
    Refused,
    SupplyDropped,
    SupplyTaken,
    TakeSupply,
    Wait,
)
from minetoofar.sim.game import Game
from minetoofar.sim.traps import Trap
from tests.helpers import MINER, make_game

ROOM = ["#########", "#.......#", "#.......#", "#.......#", "#...<...#", "#.......#", "#########"]
KIT = SupplyLine("patch_up_kit", 2, 0)
FIZZ = SupplyLine("overtime_fizz", 1, 0)
JACKET = SupplyLine("welders_jacket", 1, 16)
DROP = SupplyDrop(2, (KIT, FIZZ, JACKET))


def wait(g: Game, turns: int) -> list[object]:
    events: list[object] = []
    for _ in range(turns):
        events += g.submit(Wait())
    return events


def landed() -> Game:
    g = make_game(ROOM, supply=[DROP])
    wait(g, 2)
    return g


# -- landing ------------------------------------------------------------------------------------


def test_nothing_lands_before_its_turn_and_a_crate_does_on_it() -> None:
    g = make_game(ROOM, supply=[DROP])
    assert not any(isinstance(e, SupplyDropped) for e in wait(g, 1)) and g.crates == []
    events = wait(g, 1)
    assert SupplyDropped(Pos(3, 3), 1) in events
    assert [(c.pos, c.number) for c in g.crates] == [(Pos(3, 3), 1)]


def test_the_crate_lands_on_the_first_free_floor_tile_nearest_the_player_in_row_order() -> None:
    g = landed()
    assert g.crates[0].pos == Pos(3, 3)  # ring one, top row first, left to right


def test_it_skips_tiles_that_are_taken() -> None:
    g = make_game(ROOM, [(MINER, (3, 3), "asleep")], supply=[DROP])
    g.monsters[0].ready_at = 10**9
    g.floor.append(FloorItem(Pos(4, 3), Item("prybar")))
    g.traps.append(Trap(Pos(5, 3), "spring_trap"))
    wait(g, 2)
    assert g.crates[0].pos == Pos(3, 4)  # the next free one in row order


def test_a_second_crate_does_not_land_on_the_first() -> None:
    g = make_game(ROOM, supply=[DROP, SupplyDrop(3, (FIZZ,))])
    wait(g, 3)
    assert {c.pos for c in g.crates} == {Pos(3, 3), Pos(4, 3)} and [c.number for c in g.crates] == [
        1,
        2,
    ]


def test_a_drop_with_no_room_within_three_tiles_waits_for_some() -> None:
    rows = ["#####", "#.<.#", "#####"]
    g = make_game(rows, supply=[SupplyDrop(1, (FIZZ,))])
    g.floor += [FloorItem(Pos(1, 1), Item("prybar")), FloorItem(Pos(3, 1), Item("prybar"))]
    wait(g, 3)
    assert g.crates == []  # nowhere free; the crate is still on its way
    g.floor.clear()
    events = wait(g, 1)
    assert any(isinstance(e, SupplyDropped) for e in events) and len(g.crates) == 1


def test_the_crate_is_in_the_view_once_seen() -> None:
    g = landed()
    assert [(c.pos, c.number) for c in g.view().crates] == [(Pos(3, 3), 1)]


# -- opening and taking -----------------------------------------------------------------------


def test_stepping_onto_the_crate_opens_the_invoice() -> None:
    g = landed()
    g.player.pos = Pos(4, 3)
    assert AtCrate(1) in g.submit(Move(-1, 0))
    assert g.crate_here() is g.crates[0]


def test_asking_for_it_again_costs_no_time() -> None:
    g = landed()
    g.player.pos = Pos(3, 3)
    before = g.ticks
    assert g.submit(Pickup()) == [AtCrate(1)] and g.ticks == before


def test_taking_lines_hands_over_prepaid_stock_and_bills_the_invoice_to_the_slip() -> None:
    g = landed()
    g.player.pos = Pos(3, 3)
    events = g.submit(TakeSupply((0, 2)))
    assert SupplyTaken(1, 10 + 22, 7, 2) in events
    assert Item("patch_up_kit", 2, 0) in g.player.pack
    assert Item("welders_jacket", 1, 0, 16) in g.player.pack
    assert g.ledger.supply == [("Supply Drop Invoice #1", 10 + 22 + 7 + 2)]
    assert [ln.item for ln in g.crates[0].lines] == ["overtime_fizz"]
    slip = g.slip()
    assert {line.key: line.owed for line in slip.adjustments}["supply:1"] == 41


def test_prepaid_stock_merges_with_other_prepaid_stock_only() -> None:
    g = landed()
    g.player.pos = Pos(3, 3)
    g.submit(TakeSupply((0,)))
    assert [i for i in g.player.pack if i.id == "patch_up_kit"] == [
        Item("patch_up_kit", 2, 5),
        Item("patch_up_kit", 2, 0),
    ]


def test_the_delivery_fee_is_billed_once_per_crate() -> None:
    g = landed()
    g.player.pos = Pos(3, 3)
    g.submit(TakeSupply((0,)))
    events = g.submit(TakeSupply((0, 1)))  # the Fizz and the Jacket, what is left
    assert SupplyTaken(1, 29, 6, 0) in events
    assert g.ledger.supply == [("Supply Drop Invoice #1", 14), ("Supply Drop Invoice #1", 35)]
    assert g.crates == []  # empty, so gone


def test_taking_costs_a_turn() -> None:
    g = landed()
    g.player.pos = Pos(3, 3)
    before = g.ticks
    g.submit(TakeSupply((1,)))
    assert g.ticks == before + 100


def test_a_pack_that_cannot_hold_the_lot_refuses_the_whole_order() -> None:
    g = landed()
    g.player.pos = Pos(3, 3)
    g.player.pack[:] = [Item("overtime_fizz", 2, 4)]  # two is the most you may carry
    before = g.state_hash()
    assert g.submit(TakeSupply((1,))) == [Refused("pack_full")]
    assert g.state_hash() == before and len(g.crates[0].lines) == 3


def test_bad_orders_are_refused_for_free() -> None:
    g = landed()
    assert g.submit(TakeSupply((0,))) == [Refused("no_crate")]  # not standing on it
    g.player.pos = Pos(3, 3)
    assert g.submit(TakeSupply(())) == [Refused("nothing_taken")]
    assert g.submit(TakeSupply((9,))) == [Refused("no_item")]
    assert g.submit(TakeSupply((0, 0))) == [Refused("no_item")]  # a line only once
    assert g.ticks == 200


def test_the_state_hash_notices_crates_and_what_is_still_to_come() -> None:
    a, b = make_game(ROOM, supply=[DROP]), make_game(ROOM, supply=[DROP, SupplyDrop(5, (FIZZ,))])
    assert a.state_hash() != b.state_hash()
    before = a.state_hash()
    wait(a, 2)
    assert a.state_hash() != before
