import pytest

from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.geometry import Pos
from minetoofar.sim.actors import (
    max_hp,
    modifier,
    new_monster,
    new_player,
    offhand_stats,
    player_stats,
    scaled_monster_stats,
)
from minetoofar.sim.combat import Stats

DATA = load_gamedata()
HERE = Pos(3, 4)


@pytest.mark.parametrize(
    ("score", "mod"), [(16, 3), (10, 0), (13, 1), (9, -1), (8, -1), (7, -2), (11, 0), (18, 4)]
)
def test_attribute_modifier_floors_halves(score: int, mod: int) -> None:
    assert modifier(score) == mod


def test_fighter_rank_one_numbers_match_the_gdd_kit_table() -> None:
    player = new_player(DATA, "fighter", rank=1, pos=HERE)
    assert (player.hp, player.max_hp) == (30, 30)
    assert player_stats(player, DATA) == Stats(
        atk=5, defense=1, dr=2, dice_n=1, dice_sides=8, dmg_flat=3, attack_cost=100
    )


@pytest.mark.parametrize(
    ("rank", "hp", "atk", "dmg_flat"),
    [(1, 30, 5, 3), (2, 35, 6, 3), (3, 35, 6, 3), (4, 40, 6, 4), (5, 45, 6, 4)],
)
def test_fighter_progression_matches_gdd_6_4(rank: int, hp: int, atk: int, dmg_flat: int) -> None:
    player = new_player(DATA, "fighter", rank=rank, pos=HERE)
    stats = player_stats(player, DATA)
    assert (player.max_hp, stats.atk, stats.dmg_flat) == (hp, atk, dmg_flat)
    assert max_hp(DATA, "fighter", rank) == hp


@pytest.mark.parametrize("rank", [0, 6, -1])
def test_rank_outside_one_to_five_is_rejected(rank: int) -> None:
    with pytest.raises(ValueError, match="rank"):
        new_player(DATA, "fighter", rank=rank, pos=HERE)


def test_broken_armor_loses_its_dr_and_def() -> None:
    player = new_player(DATA, "fighter", rank=1, pos=HERE)
    assert player.body_dur == 18
    player.body_dur = 0
    stats = player_stats(player, DATA)
    assert (stats.dr, stats.defense) == (0, 1)  # the shield's +1 stays


def test_player_gets_the_class_default_name_and_starts_unhurt() -> None:
    player = new_player(DATA, "fighter", rank=1, pos=HERE)
    assert player.name == "Hale" and player.id == 0 and player.pos == HERE
    assert player.ready_at == 0 and not player.stubborn_used


def test_level_one_miner_has_base_stats() -> None:
    stats, hp = scaled_monster_stats(DATA.monsters["shambling_miner"], level=1)
    assert hp == 12
    assert stats == Stats(
        atk=2, defense=0, dr=0, dice_n=1, dice_sides=6, dmg_flat=1, attack_cost=100
    )


def test_level_five_miner_matches_the_gdd_worked_example() -> None:
    stats, hp = scaled_monster_stats(DATA.monsters["shambling_miner"], level=5)
    assert hp == 17  # 12 * 148 // 100
    assert (stats.atk, stats.dice_n, stats.dice_sides, stats.dmg_flat) == (4, 1, 6, 3)


@pytest.mark.parametrize(
    ("level", "hp", "atk", "flat"),
    [(1, 12, 2, 1), (2, 13, 2, 1), (3, 14, 3, 2), (4, 16, 3, 2), (5, 17, 4, 3)],
)
def test_monster_scaling_by_level(level: int, hp: int, atk: int, flat: int) -> None:
    stats, got_hp = scaled_monster_stats(DATA.monsters["shambling_miner"], level)
    assert (got_hp, stats.atk, stats.dmg_flat) == (hp, atk, flat)


def test_new_monster_records_kind_state_and_speed() -> None:
    miner = new_monster(DATA, "shambling_miner", ident=3, pos=HERE, state="asleep", level=2)
    assert (miner.id, miner.kind, miner.state, miner.name) == (
        3,
        "shambling_miner",
        "asleep",
        "Shambling Miner",
    )
    assert (miner.hp, miner.max_hp, miner.move_cost, miner.sight) == (13, 13, 150, 5)


# -- every number in GDD 6.3 (Rank 1 kits) and 6.4 (progression), for all three classes ----------

# class: (HP by rank, ATK by rank, damage bonus by rank, DEF, DR, dice sides)
GDD_TABLE = {
    "fighter": ((30, 35, 35, 40, 45), (5, 6, 6, 6, 6), (3, 3, 3, 4, 4), 1, 2, 8),
    "rogue": ((22, 26, 26, 30, 34), (5, 6, 6, 6, 6), (3, 3, 3, 4, 4), 5, 0, 6),
    "ranger": ((26, 30, 30, 34, 38), (3, 4, 4, 4, 4), (1, 1, 1, 2, 2), 2, 1, 6),
}


@pytest.mark.parametrize("class_id", GDD_TABLE)
@pytest.mark.parametrize("rank", [1, 2, 3, 4, 5])
def test_derived_stats_match_the_gdd_tables_at_every_rank(class_id: str, rank: int) -> None:
    hp, atk, flat, defense, dr, sides = GDD_TABLE[class_id]
    player = new_player(DATA, class_id, rank=rank, pos=HERE)
    stats = player_stats(player, DATA)
    i = rank - 1
    assert (player.max_hp, player.hp) == (hp[i], hp[i])
    assert (stats.atk, stats.dmg_flat) == (atk[i], flat[i])
    assert (stats.defense, stats.dr, stats.dice_n, stats.dice_sides) == (defense, dr, 1, sides)
    assert stats.attack_cost == 100


@pytest.mark.parametrize("rank", [1, 2, 3, 4, 5])
def test_the_rangers_off_hand_attacks_at_minus_four_with_no_attribute_damage(rank: int) -> None:
    player = new_player(DATA, "ranger", rank=rank, pos=HERE)
    main, off = player_stats(player, DATA), offhand_stats(player, DATA)
    assert off is not None
    assert off.atk == main.atk - 4  # GDD 6.3: +3 main, -1 off-hand at Rank 1
    assert off.dmg_flat == main.dmg_flat - 1  # the +1 STR modifier does not apply
    assert (off.dice_n, off.dice_sides, off.dr, off.defense) == (1, 6, main.dr, main.defense)


def test_rank_one_ranger_off_hand_is_minus_one() -> None:
    assert offhand_stats(new_player(DATA, "ranger", 1, HERE), DATA).atk == -1  # type: ignore[union-attr]


def test_dual_strike_can_drop_the_off_hand_penalty() -> None:
    player = new_player(DATA, "ranger", rank=3, pos=HERE)
    full = offhand_stats(player, DATA, penalty=0)
    assert full is not None and full.atk == player_stats(player, DATA).atk


@pytest.mark.parametrize("class_id", ["fighter", "rogue"])
def test_only_two_handed_hatchets_make_an_off_hand_attack(class_id: str) -> None:
    assert offhand_stats(new_player(DATA, class_id, 1, HERE), DATA) is None  # shield / empty


def test_a_finesse_weapon_uses_the_better_attribute() -> None:
    rogue = new_player(DATA, "rogue", rank=1, pos=HERE)
    assert player_stats(rogue, DATA).atk == 2 + 3  # DEX +3 beats STR +0


def test_each_class_starts_facing_south_and_has_its_own_name() -> None:
    names = {c: new_player(DATA, c, 1, HERE).name for c in GDD_TABLE}
    assert names == {"fighter": "Hale", "rogue": "Rook", "ranger": "Wren"}
    assert all(new_player(DATA, c, 1, HERE).facing == (0, 1) for c in GDD_TABLE)


def test_monsters_know_their_faction_and_facing() -> None:
    vermin = new_monster(
        DATA, "cave_vermin", ident=1, pos=HERE, state="idle", level=1, facing=(1, 0)
    )
    assert (vermin.faction, vermin.facing) == ("beast", (1, 0))
    assert new_monster(DATA, "shambling_miner", 2, HERE, "idle", 1).faction == "undead"


def test_monsters_carry_their_behavior_and_hide_when_buried_or_submerged() -> None:
    eel = new_monster(DATA, "blind_ore_eel", ident=1, pos=HERE, state="submerged", level=1)
    miner = new_monster(DATA, "shambling_miner", ident=2, pos=HERE, state="buried", level=1)
    seen = new_monster(DATA, "shambling_miner", ident=3, pos=HERE, state="idle", level=1)
    assert (eel.behavior, miner.behavior) == ("eel", "hunter")
    assert eel.hidden and miner.hidden and not seen.hidden


def test_humans_get_their_speech_and_vane_gets_his_traps() -> None:
    speech = {"on_sight": "Hello."}
    vane = new_monster(DATA, "prospector_vane", 1, HERE, "idle", 1, speech=speech, traps_left=4)
    assert (vane.speech, vane.traps_left, vane.said) == (speech, 4, {})
    assert (vane.max_hp, vane.stats.atk, vane.stats.defense) == (32, 4, 4)
    grimsby = new_monster(DATA, "foreman_grimsby", 2, HERE, "idle", 5)
    assert (grimsby.max_hp, grimsby.stats.atk, grimsby.stats.dmg_flat) == (
        40 * 148 // 100,
        6,
        2 + 2,
    )
