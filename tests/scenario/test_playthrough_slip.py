"""M6 done criterion: finishing a level shows a pay slip whose lines match what actually happened.

One scripted level on a graveyard floor: a torch is lit, two nuggets and a gem are pocketed, a
coupon is read, a hidden Spring Trap goes off, a kit is drunk, a Miner scuffs the armor before it
falls, and Prospector Vane is put down for the bounty and the ingot he was carrying."""

from minetoofar.core.geometry import Pos
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.economy import Choices
from minetoofar.sim.events import (
    ArmorDamaged,
    DocumentRead,
    Healed,
    HumanDefeated,
    ItemUsed,
    Move,
    Pickup,
    ToggleTorch,
    TrapTriggered,
    UseItem,
    ValuableCollected,
)
from minetoofar.sim.game import Game
from minetoofar.sim.traps import Trap
from tests.helpers import BALANCE, MINER, ScriptedRng, make_game

E = Move(1, 0)
ROWS = ["#" * 26, "#<" + "." * 22 + ">#", "#" * 26]


def face(n: int) -> int:
    return n - 1


def level() -> Game:
    floor = [
        FloorItem(Pos(2, 1), Item("silver_nugget")),
        FloorItem(Pos(3, 1), Item("silver_nugget")),
        FloorItem(Pos(4, 1), Item("rough_gem")),
        FloorItem(Pos(8, 1), Item("coupon", text=0)),
    ]
    rng = ScriptedRng([
        face(2),  # the passive look for the hidden trap beside us: not this time (1 in 3)
        face(5),  # the Spring Trap: 5 + 2, less the Hard Hat's 2
        face(15), face(5),  # we hit the Miner for 8 (it has 14) ...
        face(15), face(3), # ... it hits back: 1d6+1 = 4, less DR 2 ...
        face(15), face(5),  # ... and we finish it
        face(15), face(5),  # one blow puts Vane down
    ])  # fmt: skip
    g = make_game(
        ROWS, [(MINER, (12, 1), "asleep"), ("prospector_vane", (22, 1), "asleep")], rng,
        level=3, graveyard=True, floor=floor, traps=[Trap(Pos(6, 1), "spring_trap")],
        drops={2: [Item("silver_ingot")]},
    )  # fmt: skip
    g.monsters[1].hp = g.monsters[1].max_hp = 3
    for m in g.monsters:
        m.ready_at = 10**9  # asleep for good until the scene reaches them
    return g


def walk(g: Game, steps: int) -> list[object]:
    events: list[object] = []
    for _ in range(steps):
        events += g.submit(E)
    return events


def test_the_slip_lists_exactly_what_happened() -> None:
    g = level()
    seen: list[object] = []
    seen += g.submit(ToggleTorch())  # an issued torch: 2g
    seen += walk(g, 3)  # nugget, nugget, gem
    seen += walk(g, 2)  # x=5 (looks for the trap), x=6 (the Spring Trap)
    assert g.player.hp == 30 - 5
    seen += g.submit(UseItem(0))  # an issued kit: 5g, heals the 5 we lost
    seen += walk(g, 2)  # x=8 is the coupon
    seen += g.submit(Pickup())
    seen += walk(g, 3)  # x=11, beside the Miner
    g.monsters[0].state, g.monsters[0].ready_at = "hunting", g.ticks  # it wakes to meet us
    seen += g.submit(E)  # the first blow
    assert g.monsters[0].hp == 6  # a Level 3 Miner has 14
    seen += g.submit(E)  # the second
    assert [m.kind for m in g.monsters] == ["prospector_vane"]
    seen += walk(g, 10)  # on to Vane (x=22)
    seen += g.submit(E)  # one blow puts him down
    seen += walk(g, 1)  # and his ingot is ours

    kinds = [type(e) for e in seen]
    assert kinds.count(ValuableCollected) == 4 and ItemUsed in kinds and TrapTriggered in kinds
    assert Healed in kinds and DocumentRead in kinds and HumanDefeated in kinds
    assert ArmorDamaged in kinds

    s = g.slip()
    assert [(line.label, line.owed) for line in s.gross_lines] == [
        ("Base Job Fee", BALANCE.economy.base_fee),
        ("Hazard Premium", 5),
        ("Unauthorized Personnel Retrieval Bounty", 6),
        ("Salvage Credit: Silver Nugget x2 @2g", 4),
        ("Salvage Credit: Rough Gem x1 @4g", 4),
        ("Salvage Credit: Silver Ingot x1 @6g", 6),
    ]
    assert [(line.label, line.owed) for line in s.adjustments] == [
        ("Armor repair: Boiler Suit, 1 pts", 1),
        ("Consumables: Torch x1 @2g", 2),
        ("Consumables: Patch-Up Kit x1 @5g", 5),
        ("Hazard Surcharge", 3),
    ]
    gross = BALANCE.economy.base_fee + 5 + 6 + 4 + 4 + 6
    assert (s.gross, s.adjusted, s.net) == (gross, 11, gross - 11)


def test_the_coupon_found_on_the_way_is_worth_three_gold_on_that_slip() -> None:
    g = level()
    g.submit(ToggleTorch())
    walk(g, 5)
    g.submit(UseItem(0))
    walk(g, 2)
    g.submit(Pickup())
    assert g.account.coupons == 1
    s = g.check_out(Choices(coupons=("hazard_surcharge",)))
    assert s.adjusted == 2 + 5 + 0 and g.account.coupons == 0
