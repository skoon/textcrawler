"""The scripted player picks things up and patches itself up, so replays and balance runs cover
the pack."""

from minetoofar.core.geometry import Pos
from minetoofar.core.seed import Seed
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.bot import choose, play
from minetoofar.sim.events import Command, Event, Pickup, TakeSupply, UseItem
from minetoofar.sim.game import Game
from tests.helpers import MINER, ScriptedRng, make_game

ROOM = ["#" * 12, "#<........>#", "#" * 12]


def run(game: Game, limit: int = 200) -> list[Command]:
    sent: list[Command] = []

    def submit(command: Command) -> list[Event]:
        sent.append(command)
        return game.submit(command)

    play(game, submit, limit)
    return sent


def test_the_bot_walks_to_loot_before_it_leaves() -> None:
    game = make_game(ROOM, floor=[FloorItem(Pos(5, 1), Item("rough_gem"))])
    run(game)
    assert game.floor == [] and game.ledger.salvage[0].kind == "rough_gem"
    assert game.pos == game.spec.exit


def test_the_bot_picks_up_what_it_stands_on_and_reads_documents() -> None:
    game = make_game(ROOM, floor=[
        FloorItem(Pos(3, 1), Item("prybar")), FloorItem(Pos(6, 1), Item("coupon")),
        FloorItem(Pos(8, 1), Item("patch_up_kit", 1, 3)),
    ])  # fmt: skip
    sent = run(game)
    assert game.floor == [] and sent.count(Pickup()) == 3
    assert any(i.id == "prybar" for i in game.player.pack) and game.account.coupons == 1


def test_the_bot_does_not_loop_on_what_it_cannot_carry() -> None:
    game = make_game(
        ROOM, floor=[FloorItem(Pos(4, 1), Item("torch", 1, 1))], pack=[Item("torch", 3, 2)]
    )
    sent = run(game)
    assert len(sent) < 20 and game.pos == game.spec.exit and len(game.floor) == 1


def test_the_bot_drinks_a_kit_when_badly_hurt() -> None:
    game = make_game(ROOM)
    game.player.hp = 10
    assert choose(game) == UseItem(0)  # the issued kits are slot a
    game.player.hp = 25
    assert choose(game) != UseItem(0)


def test_the_bot_does_not_waste_a_kit_without_one() -> None:
    game = make_game(ROOM, pack=[])
    game.player.hp = 3
    assert not isinstance(choose(game), UseItem)


def test_fighting_beside_a_foe_still_comes_before_looting() -> None:
    game = make_game(
        ROOM, [(MINER, (2, 1), "hunting")], ScriptedRng([14, 4, 0, 0, 0, 0]),
        floor=[FloorItem(Pos(1, 1), Item("prybar"))],
    )  # fmt: skip
    cmd = choose(game)
    assert cmd != Pickup()


def test_a_whole_generated_level_is_played_without_looping() -> None:
    for seed in ("GOLD0001", "GOLD0002", "GOLD0003"):
        game = Game.new(Seed.parse(seed), 2)
        sent = run(game, 2500)
        assert len(sent) < 2500 or game.dead


# -- supply crates ------------------------------------------------------------------------------


def test_the_bot_walks_to_a_crate_and_takes_what_fits() -> None:
    from minetoofar.gen.drops import SupplyDrop, SupplyLine

    drop = SupplyDrop(1, (SupplyLine("patch_up_kit", 2, 0), SupplyLine("welders_jacket", 1, 16)))
    game = make_game(["#" * 12, "#<........>#", "#" * 12], supply=[drop])
    sent = run(game)
    assert game.crates == [] and game.pos == game.spec.exit
    assert any(i.id == "welders_jacket" for i in game.player.pack)
    assert len(game.ledger.supply) == 1
    assert sum(isinstance(c, TakeSupply) for c in sent) == 1


def test_the_bot_leaves_what_it_cannot_carry_and_does_not_loop() -> None:
    from minetoofar.gen.drops import SupplyDrop, SupplyLine

    drop = SupplyDrop(1, (SupplyLine("overtime_fizz", 2, 0),))
    game = make_game(
        ["#" * 12, "#<........>#", "#" * 12], supply=[drop], pack=[Item("overtime_fizz", 2, 4)]
    )
    sent = run(game, 100)
    assert len(game.crates) == 1 and game.pos == game.spec.exit and len(sent) < 40
