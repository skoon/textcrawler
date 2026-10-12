"""What the Requisitions Desk sells that stays with you: weapon edge, armor plating, max HP."""

from minetoofar.sim.actors import Item
from minetoofar.sim.events import Equip, SetRank
from tests.helpers import make_game

ROOM = ["#####", "#<..#", "#####"]


def test_weapon_mods_add_damage_and_attack() -> None:
    g = make_game(ROOM)
    base = g.view().hero
    g.player.weapon_mods["company_pickaxe"] = (2, 1)  # (damage, attack)
    hero = g.view().hero
    assert hero.damage == "1d8+5" and hero.atk == base.atk + 1


def test_the_mods_stay_with_the_weapon_not_the_hand() -> None:
    g = make_game(ROOM, pack=[Item("prybar")])
    g.player.weapon_mods["company_pickaxe"] = (3, 2)
    g.submit(Equip(0))  # the Prybar: no edge on it
    assert g.view().hero.damage == "1d6+3"
    g.player.weapon = "company_pickaxe"
    assert g.view().hero.damage == "1d8+6"


def test_a_sharpened_off_hand_weapon_counts_too() -> None:
    g = make_game(ROOM, class_id="ranger")
    g.player.weapon_mods["hatchet"] = (1, 0)
    assert g.view().hero.damage == "1d6+2" and g.view().hero.offhand_attack == "ATK -1  DMG 1d6+1"


def test_plated_armor_has_one_more_dr_and_four_more_dur() -> None:
    g = make_game(ROOM)
    base = g.view().hero
    g.player.plated.add("boiler_suit")
    hero = g.view().hero
    assert (hero.dr, hero.armor_max) == (base.dr + 1, base.armor_max + 4)


def test_the_repair_bill_counts_missing_points_against_the_plated_maximum() -> None:
    g = make_game(ROOM)
    g.player.plated.add("boiler_suit")
    g.player.body_dur = 18  # 4 short of 22: ceil(4 * 2 / 4)
    assert {line.key: line.owed for line in g.slip().adjustments} == {"repair": 2}
    g.check_out()
    assert g.player.body_dur == 22


def test_broken_plated_armor_loses_its_plate_too() -> None:
    g = make_game(ROOM)
    g.player.plated.add("boiler_suit")
    g.player.body_dur = 0
    assert g.view().hero.dr == 0


def test_bonus_hit_points_ride_on_top_of_rank_and_trinket() -> None:
    g = make_game(ROOM, pack=[Item("thermos")])
    g.player.hp_bonus = 3
    g.submit(SetRank(2))
    assert g.player.max_hp == 35 + 3
    g.submit(Equip(0))
    assert g.player.max_hp == 35 + 3 + 3


def test_the_state_hash_notices_every_upgrade() -> None:
    base = make_game(ROOM).state_hash()
    for change in (
        lambda p: p.weapon_mods.update({"company_pickaxe": (1, 0)}),
        lambda p: p.plated.add("boiler_suit"),
        lambda p: setattr(p, "hp_bonus", 3),
    ):
        g = make_game(ROOM)
        change(g.player)
        assert g.state_hash() != base
