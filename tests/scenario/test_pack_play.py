"""Picking up, using, equipping and dropping things on hand-drawn maps (GDD 8.1-8.3)."""

import pytest

from minetoofar.core.geometry import Pos
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.events import (
    DropItem,
    Equip,
    Equipped,
    Healed,
    ItemDropped,
    ItemPicked,
    ItemUsed,
    Move,
    Moved,
    Pickup,
    Refused,
    UseItem,
    ValuableCollected,
    Wait,
)
from minetoofar.sim.ledger import Salvage, Use
from minetoofar.sim.statuses import is_active
from tests.helpers import make_game

ROOM = ["#########", "#<......#", "#########"]
KIT, TORCH = "patch_up_kit", "torch"
E = Move(1, 0)


def at(x: int, *items: Item) -> list[FloorItem]:
    return [FloorItem(Pos(x, 1), i) for i in items]


# -- valuables jump into the pack ----------------------------------------------------------


def test_stepping_on_a_valuable_collects_it_for_free() -> None:
    g = make_game(ROOM, floor=at(2, Item("silver_nugget")))
    events = g.submit(E)
    assert events == [
        Moved(Pos(2, 1), g.grid.get(2, 1)),
        ValuableCollected("silver_nugget", "Silver Nugget", 2),
    ]
    assert g.floor == [] and g.ticks == 100
    assert g.ledger.salvage == [Salvage("silver_nugget", "Silver Nugget", 2, 1)]


def test_valuables_of_a_kind_add_up_in_the_ledger() -> None:
    g = make_game(ROOM, floor=at(2, Item("rough_gem")) + at(3, Item("rough_gem")))
    g.submit(E)
    g.submit(E)
    assert g.ledger.salvage == [Salvage("rough_gem", "Rough Gem", 4, 2)]


def test_other_valuable_kinds_are_listed_in_the_order_found() -> None:
    g = make_game(ROOM, floor=at(2, Item("cut_gem")) + at(3, Item("silver_nugget")))
    g.submit(E)
    g.submit(E)
    assert [s.kind for s in g.ledger.salvage] == ["cut_gem", "silver_nugget"]


# -- the floor ---------------------------------------------------------------------------


def test_pickup_takes_a_consumable_into_its_own_stack_for_fifty_ticks() -> None:
    g = make_game(ROOM, floor=at(1, Item(KIT, 1, 3)))
    assert g.submit(Pickup()) == [ItemPicked(KIT, "Patch-Up Kit", 1)]
    assert g.player.pack == [Item(KIT, 2, 5), Item(TORCH, 1, 2), Item(KIT, 1, 3)]
    assert g.floor == [] and g.ticks == 50


def test_pickup_with_nothing_there_is_refused_for_free() -> None:
    g = make_game(ROOM)
    assert g.submit(Pickup()) == [Refused("nothing_here")]
    assert g.ticks == 0


def test_a_full_pack_leaves_the_item_where_it_lies() -> None:
    g = make_game(ROOM, floor=at(1, Item("torch", 1, 1)), pack=[Item(TORCH, 3, 2)])
    assert g.submit(Pickup()) == [Refused("pack_full")]
    assert len(g.floor) == 1 and g.ticks == 0


def test_found_armor_keeps_its_condition() -> None:
    g = make_game(ROOM, floor=at(1, Item("welders_jacket", 1, 0, 9)))
    g.submit(Pickup())
    assert Item("welders_jacket", 1, 0, 9) in g.player.pack


def test_pickup_takes_one_thing_at_a_time() -> None:
    g = make_game(ROOM, floor=at(1, Item("prybar"), Item("hatchet")))
    g.submit(Pickup())
    assert [f.item.id for f in g.floor] == ["hatchet"]
    g.submit(Pickup())
    assert g.floor == [] and g.ticks == 100


# -- using consumables -------------------------------------------------------------------


def test_a_kit_heals_ten_and_is_billed_at_its_use_charge() -> None:
    g = make_game(ROOM)
    g.player.hp = 15
    events = g.submit(UseItem(0))
    assert events == [Healed(10), ItemUsed(KIT, "Patch-Up Kit", 5)]
    assert g.player.hp == 25 and g.ticks == 100
    assert g.player.pack[0] == Item(KIT, 1, 5)
    assert g.ledger.used == [Use(KIT, "Patch-Up Kit", 5, 1)]


def test_a_kit_never_heals_past_the_maximum() -> None:
    g = make_game(ROOM)
    g.player.hp = 25
    assert g.submit(UseItem(0))[0] == Healed(5)
    assert g.player.hp == 30


def test_a_kit_at_full_health_is_refused_and_not_wasted() -> None:
    g = make_game(ROOM)
    assert g.submit(UseItem(0)) == [Refused("full_hp")]
    assert g.player.pack[0] == Item(KIT, 2, 5) and g.ticks == 0 and g.ledger.used == []


def test_the_same_item_at_different_charges_is_billed_per_stack() -> None:
    g = make_game(ROOM, pack=[Item(KIT, 1, 3), Item(KIT, 1, 0)])
    g.player.hp = 5
    g.submit(UseItem(0))
    g.submit(UseItem(0))  # the first stack is gone, so this is the prepaid one
    assert g.ledger.used == [Use(KIT, "Patch-Up Kit", 3, 1), Use(KIT, "Patch-Up Kit", 0, 1)]


def test_equipment_is_not_usable_and_a_bad_slot_is_refused() -> None:
    g = make_game(ROOM, pack=[Item("prybar")])
    assert g.submit(UseItem(0)) == [Refused("not_usable")]
    assert g.submit(UseItem(5)) == [Refused("no_item")]
    assert g.ticks == 0


def test_overtime_fizz_makes_the_next_actions_cost_sixty_percent_for_eight_turns() -> None:
    g = make_game(ROOM, pack=[Item("overtime_fizz", 1, 4)])
    assert g.submit(UseItem(0)) == [ItemUsed("overtime_fizz", "Overtime Fizz", 4)]
    assert is_active(g.player, "overtime", g.ticks)
    start = g.ticks
    g.submit(Wait())
    assert g.ticks - start == 60
    g.player.ready_at = start + 800
    assert not is_active(g.player, "overtime", g.ticks)


def test_detergent_coat_lasts_fifty_turns() -> None:
    g = make_game(ROOM, pack=[Item("sanctified_detergent", 1, 3)])
    g.submit(UseItem(0))
    state = g.player.statuses["detergent"]
    assert state.ends == g.ticks - 100 + 5000


# -- equipment ----------------------------------------------------------------------------


def test_equipping_a_weapon_swaps_it_with_the_main_hand() -> None:
    g = make_game(ROOM, pack=[Item("prybar")])
    assert g.submit(Equip(0)) == [Equipped("Prybar")]
    assert g.player.weapon == "prybar" and g.player.pack == [Item("company_pickaxe")]
    assert g.ticks == 100


def test_a_light_weapon_can_go_in_the_off_hand_and_the_shield_goes_to_the_pack() -> None:
    g = make_game(ROOM, pack=[Item("utility_knife")])
    g.submit(Equip(0, off_hand=True))
    assert g.player.offhand == "utility_knife" and g.player.pack == [Item("sheet_metal_shield")]


def test_only_light_weapons_go_in_the_off_hand() -> None:
    g = make_game(ROOM, pack=[Item("prybar")])
    assert g.submit(Equip(0, off_hand=True)) == [Refused("not_light")]
    assert g.player.offhand == "sheet_metal_shield" and g.ticks == 0


def test_a_two_handed_weapon_puts_the_off_hand_away() -> None:
    g = make_game(ROOM, pack=[Item("sledgehammer")])
    g.submit(Equip(0))
    assert g.player.weapon == "sledgehammer" and g.player.offhand == ""
    assert Item("sheet_metal_shield") in g.player.pack


def test_nothing_goes_in_the_off_hand_while_a_two_handed_weapon_is_wielded() -> None:
    g = make_game(ROOM, pack=[Item("sledgehammer"), Item("riot_shield"), Item("hatchet")])
    g.submit(Equip(0))
    assert g.submit(
        Equip(next(i for i, x in enumerate(g.player.pack) if x.id == "riot_shield"))
    ) == [Refused("two_handed")]
    assert g.submit(Equip(0, off_hand=True))[0] == Refused("two_handed")


def test_a_shield_replaces_the_off_hand_item() -> None:
    g = make_game(ROOM, pack=[Item("riot_shield")])
    g.submit(Equip(0))
    assert g.player.offhand == "riot_shield" and g.player.pack == [Item("sheet_metal_shield")]


def test_armor_swaps_keep_each_ones_condition() -> None:
    g = make_game(ROOM, pack=[Item("welders_jacket", 1, 0, 9)])
    g.player.body_dur = 4
    g.submit(Equip(0))
    assert (g.player.body, g.player.body_dur) == ("welders_jacket", 9)
    assert g.player.pack == [Item("boiler_suit", 1, 0, 4)]


def test_a_headlamp_hat_lights_five_tiles_without_a_torch() -> None:
    g = make_game(["#" * 12, "#<" + "." * 9 + "#", "#" * 12], pack=[Item("headlamp_hard_hat")])
    assert g.light_radius == 4
    g.submit(Equip(0))
    assert g.light_radius == 5 and g.player.pack == [Item("hard_hat")]


def test_a_torch_beats_any_lamp() -> None:
    g = make_game(ROOM, pack=[Item("headlamp_hard_hat"), Item(TORCH, 1, 2)])
    g.submit(Equip(0))
    g.torch_lit, g.player.torch_left = True, 40000
    assert g.light_radius == 8


def test_a_trinket_adds_its_attack_and_hit_points() -> None:
    g = make_game(ROOM, pack=[Item("company_challenge_coin"), Item("thermos")])
    base = g.view().hero.atk
    g.submit(Equip(0))
    assert g.view().hero.atk == base + 1
    hp = g.player.max_hp
    g.submit(Equip(0))  # the thermos replaces the coin
    assert g.player.trinket == "thermos" and g.player.max_hp == hp + 3 and g.player.hp == hp + 3
    assert g.view().hero.atk == base and g.player.pack == [Item("company_challenge_coin")]


def test_taking_the_thermos_off_trims_current_hit_points() -> None:
    g = make_game(ROOM, pack=[Item("thermos"), Item("laminated_lanyard")])
    g.submit(Equip(0))
    assert g.player.max_hp == 33 and g.player.hp == 33
    g.submit(Equip(0))
    assert g.player.max_hp == 30 and g.player.hp == 30


def test_a_thermos_does_not_heal_the_wounded_beyond_three() -> None:
    g = make_game(ROOM, pack=[Item("thermos")])
    g.player.hp = 10
    g.submit(Equip(0))
    assert g.player.hp == 13 and g.player.max_hp == 33


def test_a_consumable_is_not_equipment() -> None:
    g = make_game(ROOM)
    assert g.submit(Equip(0)) == [Refused("not_equipment")]
    assert g.submit(Equip(9)) == [Refused("no_item")]


# -- dropping -------------------------------------------------------------------------------


def test_dropping_leaves_one_unit_with_its_charge_for_fifty_ticks() -> None:
    g = make_game(ROOM)
    assert g.submit(DropItem(0)) == [ItemDropped("Patch-Up Kit")]
    assert g.floor == [FloorItem(Pos(1, 1), Item(KIT, 1, 5))]
    assert g.player.pack[0] == Item(KIT, 1, 5) and g.ticks == 50


def test_a_dropped_item_picks_back_up_into_the_same_stack() -> None:
    g = make_game(ROOM)
    g.submit(DropItem(0))
    g.submit(Pickup())
    assert g.player.pack[0] == Item(KIT, 2, 5) and g.floor == []


def test_dropping_a_missing_slot_is_refused() -> None:
    assert make_game(ROOM).submit(DropItem(7)) == [Refused("no_item")]


@pytest.mark.parametrize("slot", [0, 1])
def test_dropping_the_last_unit_removes_the_slot(slot: int) -> None:
    g = make_game(ROOM, pack=[Item(KIT, 1, 5), Item(TORCH, 1, 2)])
    g.submit(DropItem(slot))
    assert len(g.player.pack) == 1
