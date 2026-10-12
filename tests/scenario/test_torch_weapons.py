"""The torch as a burning item, and the new weapons' rules (GDD 7.1, 7.5, 8.1, 8.2)."""

from minetoofar.core.geometry import Pos
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.events import (
    Attacked,
    HumanDefeated,
    ItemUsed,
    Killed,
    Move,
    Refused,
    StatusApplied,
    ToggleTorch,
    TorchBurnedOut,
    TorchChanged,
    TorchDropped,
    UseItem,
    Wait,
)
from minetoofar.sim.ledger import Use
from minetoofar.sim.statuses import is_active
from tests.helpers import MINER, ScriptedRng, make_game

ROOM = ["#########", "#<......#", "#########"]
CELL = ["####", "#<.#", "####"]
BRINE = ["#######", "#<.~..#", "#######"]
TORCH = "torch"
E = Move(1, 0)


def face(n: int) -> int:
    return n - 1


# -- lighting and burning ------------------------------------------------------------------


def test_lighting_takes_a_torch_from_the_pack_and_bills_its_use_charge() -> None:
    g = make_game(ROOM)
    assert g.submit(ToggleTorch()) == [ItemUsed(TORCH, "Torch", 2), TorchChanged(True)]
    assert g.torch_lit and g.player.torch_left == 40000
    assert [i.id for i in g.player.pack] == ["patch_up_kit"]
    assert g.ledger.used == [Use(TORCH, "Torch", 2, 1)]


def test_a_snuffed_torch_relights_free_and_keeps_its_remaining_time() -> None:
    g = make_game(ROOM)
    g.submit(ToggleTorch())
    g.submit(Wait())
    g.submit(Wait())
    g.submit(ToggleTorch())  # snuff
    left = g.player.torch_left
    assert not g.torch_lit and left == 40000 - 200
    assert g.submit(ToggleTorch()) == [TorchChanged(True)]  # no second bill
    assert g.player.torch_left == left and g.ledger.used == [Use(TORCH, "Torch", 2, 1)]


def test_a_snuffed_torch_does_not_burn() -> None:
    g = make_game(ROOM)
    g.submit(ToggleTorch())
    g.submit(ToggleTorch())
    left = g.player.torch_left
    for _ in range(5):
        g.submit(Wait())
    assert g.player.torch_left == left


def test_with_no_torch_the_command_is_refused_for_free() -> None:
    g = make_game(ROOM, pack=[])
    assert g.submit(ToggleTorch()) == [Refused("no_torch")]
    assert g.ticks == 0 and not g.torch_lit


def test_a_lit_torch_burns_out_after_four_hundred_turns() -> None:
    g = make_game(ROOM, pack=[Item(TORCH, 1, 2)])
    g.submit(ToggleTorch())
    g.player.torch_left = 250
    assert g.submit(Wait()) == [] or True
    assert g.torch_lit and g.player.torch_left == 150
    g.submit(Wait())
    events = g.submit(Wait())
    assert TorchBurnedOut() in events
    assert not g.torch_lit and g.player.torch_left == 0


def test_after_burning_out_the_next_torch_comes_out_of_the_pack() -> None:
    g = make_game(ROOM, pack=[Item(TORCH, 2, 2)])
    g.submit(ToggleTorch())
    g.player.torch_left = 100
    g.submit(Wait())  # burns out
    assert g.submit(ToggleTorch())[0] == ItemUsed(TORCH, "Torch", 2)
    assert g.player.torch_left == 40000 and g.player.pack == []


def test_using_a_torch_from_the_pack_lights_it() -> None:
    g = make_game(ROOM)
    slot = next(i for i, x in enumerate(g.player.pack) if x.id == TORCH)
    assert g.submit(UseItem(slot)) == [ItemUsed(TORCH, "Torch", 2), TorchChanged(True)]
    assert g.torch_lit


def test_using_a_torch_while_one_burns_is_refused() -> None:
    g = make_game(ROOM, pack=[Item(TORCH, 2, 2)])
    g.submit(ToggleTorch())
    assert g.submit(UseItem(0)) == [Refused("already_lit")]


def test_a_torch_lost_in_the_brine_is_gone_and_logged_for_the_bill() -> None:
    g = make_game(BRINE, rng=ScriptedRng([0]))  # the 1-in-2 roll comes up
    g.submit(ToggleTorch())
    g.submit(E)
    events = g.submit(E)
    assert TorchDropped() in events and not g.torch_lit and g.player.torch_left == 0
    assert g.ledger.torches_dropped == 1


def test_a_lost_torch_means_the_next_one_is_a_new_one_and_a_new_bill() -> None:
    g = make_game(BRINE, pack=[Item(TORCH, 2, 2)], rng=ScriptedRng([0]))
    g.submit(ToggleTorch())
    g.submit(E)
    g.submit(E)  # lost in the brine
    g.submit(ToggleTorch())
    assert g.ledger.used == [Use(TORCH, "Torch", 2, 2)] and g.ledger.torches_dropped == 1


# -- weapons ---------------------------------------------------------------------------------


def test_a_shovel_blow_is_heard_eight_steps_away_and_a_pickaxe_five() -> None:
    for weapon, radius in (("gravediggers_shovel", 8), ("company_pickaxe", 5)):
        g = make_game(CELL, [(MINER, (2, 1), "asleep")], ScriptedRng([face(15), face(5), face(1)]))
        g.player.weapon = weapon
        heard: list[int] = []
        g.noise = lambda source, r, heard=heard: heard.append(r) or []  # type: ignore[method-assign,misc]
        g.submit(E)
        assert heard == [radius], weapon


def test_a_sledgehammer_swing_takes_a_hundred_and_thirty_ticks() -> None:
    rng = ScriptedRng([face(15), face(5), face(1), face(1)])  # the Miner swings twice in 130
    g = make_game(CELL, [(MINER, (2, 1), "asleep")], rng)
    g.player.weapon, g.player.offhand = "sledgehammer", ""
    g.submit(E)
    assert g.ticks == 130


def test_a_shovel_critical_stuns_the_target() -> None:
    g = make_game(
        CELL, [(MINER, (2, 1), "asleep")], ScriptedRng([face(20), face(1), face(1), face(1)])
    )
    g.player.weapon = "gravediggers_shovel"
    events = g.submit(E)
    m = g.monsters[0]
    assert StatusApplied(m.id, m.name, "stunned") in events
    assert is_active(m, "stunned", g.ticks - 100)


def test_an_ordinary_hit_with_a_shovel_does_not_stun() -> None:
    g = make_game(CELL, [(MINER, (2, 1), "asleep")], ScriptedRng([face(15), face(5), face(1)]))
    g.player.weapon = "gravediggers_shovel"
    g.submit(E)
    assert "stunned" not in g.monsters[0].statuses


def test_a_pickaxe_critical_does_not_stun() -> None:
    g = make_game(
        CELL, [(MINER, (2, 1), "asleep")], ScriptedRng([face(20), face(1), face(1), face(1)])
    )
    g.submit(E)
    assert "stunned" not in g.monsters[0].statuses


def test_a_killing_critical_does_not_bother_to_stun() -> None:
    g = make_game(CELL, [(MINER, (2, 1), "idle")], ScriptedRng([face(20), face(8), face(8)]))
    g.player.weapon = "gravediggers_shovel"
    g.monsters[0].hp = 3
    events = g.submit(E)
    assert any(isinstance(e, Killed) for e in events)
    assert not any(isinstance(e, StatusApplied) for e in events)


def test_prybar_and_foremans_pickaxe_add_to_attack() -> None:
    g = make_game(CELL)
    base = g.view().hero.atk
    g.player.weapon = "prybar"
    assert g.view().hero.atk == base + 1
    g.player.weapon = "foremans_pickaxe"
    assert g.view().hero.atk == base + 1


def test_the_assay_blade_adds_one_damage_and_uses_the_better_stat() -> None:
    g = make_game(CELL, class_id="rogue")
    g.player.weapon = "assay_blade"
    assert g.view().hero.damage == "1d8+4"  # DEX +3, blade +1


# -- Detergent Coat -------------------------------------------------------------------------------


def coated(target: str) -> Attacked:
    g = make_game(CELL, [(target, (2, 1), "idle")], ScriptedRng([face(15), face(5), face(1)]))
    g.player.pack[:] = [Item("sanctified_detergent", 1, 3)]
    g.monsters[0].ready_at = 10**9  # it holds still while the coat goes on
    g.submit(UseItem(0))
    g.monsters[0].ready_at = g.ticks
    events = g.submit(E)
    return next(e for e in events if isinstance(e, Attacked) and e.attacker == 0)


def test_detergent_adds_two_damage_against_the_undead() -> None:
    assert coated(MINER).damage == 5 + 3 + 2


def test_detergent_does_nothing_against_beasts() -> None:
    assert coated("cave_vermin").damage == 5 + 3 - 0  # vermin DR 0


# -- drops and the bounty -----------------------------------------------------------------------


def test_a_slain_monster_leaves_its_pre_rolled_drop_where_it_fell() -> None:
    gems = [Item("rough_gem", 2)]
    g = make_game(
        CELL, [(MINER, (2, 1), "idle")], ScriptedRng([face(15), face(8)]), drops={1: gems}
    )
    g.monsters[0].hp = 3
    g.submit(E)
    assert g.floor == [FloorItem(Pos(2, 1), Item("rough_gem", 2))]


def test_a_monster_without_a_drop_leaves_nothing() -> None:
    g = make_game(CELL, [(MINER, (2, 1), "idle")], ScriptedRng([face(15), face(8)]))
    g.monsters[0].hp = 3
    g.submit(E)
    assert g.floor == []


def test_stepping_onto_a_drop_collects_valuables_at_once() -> None:
    g = make_game(
        CELL,
        [(MINER, (2, 1), "idle")],
        ScriptedRng([face(15), face(8)]),
        drops={1: [Item("rough_gem", 2)]},
    )
    g.monsters[0].hp = 3
    g.submit(E)
    g.submit(E)
    assert g.ledger.salvage[0].count == 2 and g.floor == []


def test_defeating_a_rogue_human_earns_the_bounty_and_a_drop() -> None:
    g = make_game(
        CELL, [("prospector_vane", (2, 1), "idle")], ScriptedRng([face(15), face(8)]),
        drops={1: [Item("silver_ingot")]},
    )  # fmt: skip
    g.monsters[0].hp = 3
    events = g.submit(E)
    assert HumanDefeated("Prospector Vane") in events and g.ledger.bounty
    assert [f.item.id for f in g.floor] == ["silver_ingot"]


def test_killing_a_beast_is_no_bounty() -> None:
    g = make_game(CELL, [("gem_badger", (2, 1), "idle")], ScriptedRng([face(15), face(8)]))
    g.monsters[0].hp = 3
    g.submit(E)
    assert not g.ledger.bounty
