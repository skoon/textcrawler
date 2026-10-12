import pytest

from minetoofar.content.gamedata import DataError, found_charge, load_gamedata, parse_gamedata

CLASSES = """
[fighter]
name = "Fighter"
default_name = "Hale"
signature = "stubborn"
ability = "cleave"
blurb = "Heavy."
strength = 16
dexterity = 10
weapon = "pick"
offhand = "shield"
head = "hat"
body = "suit"
rank_hp = [30, 35, 35, 40, 45]
rank_atk = [0, 1, 1, 1, 1]
rank_dmg = [0, 0, 0, 1, 1]
"""
ITEMS = """
[weapon.pick]
name = "Pick"
dice_n = 1
dice_sides = 8
stat = "str"
atk = 0
dmg = 0
cost = 100
two_handed = 0
tier = 1
light = 0
noise = 0
stuns = 0
[armor.suit]
name = "Suit"
weight = "heavy"
dr = 2
defense = 0
dur = 18
repair_rate = 3
tier = 1
[shield.shield]
name = "Shield"
defense = 1
tier = 1
[hat.hat]
name = "Hat"
defense = 0
trap_reduction = 2
lamp = 4
tier = 1
[trinket.coin]
name = "Coin"
atk = 1
hp = 0
waives = 0
tier = 1
[consumable.kit]
name = "Kit"
price = 5
carry = 4
effect = "heal"
value = 10
status = ""
[consumable.fizz]
name = "Fizz"
price = 7
carry = 2
effect = "status"
value = 800
status = "stunned"
[valuable.nugget]
name = "Nugget"
credit = 2
weight = 50
shine = "silver"
"""
MONSTERS = """
[miner]
name = "Miner"
faction = "undead"
hp = 12
atk = 2
defense = 0
dice_n = 1
dice_sides = 6
dmg = 1
dr = 0
move_cost = 150
attack_cost = 100
sight = 5
threat = 3
behavior = "hunter"
min_level = 1
weight = 15
grave_weight = 30
"""
STATUSES = """
[stunned]
name = "Stunned"
duration_ticks = 100
delay_ticks = 100
immune_ticks = 300
cost_pct = 100
defense = 0
tick_ticks = 0
"""
ABILITIES = """
[cleave]
name = "Cleave"
kind = "cleave"
unlock_rank = 3
cooldown_ticks = 400
cooldown_ticks_up = 300
value = 2
value_up = 0
charges = 0
charges_up = 0
"""
TRAPS = """
[spring_trap]
name = "Spring Trap"
dice_n = 1
dice_sides = 6
dmg = 2
effect = "damage"
cave_in = 0
"""
GOOD = (CLASSES, ITEMS, MONSTERS, STATUSES, ABILITIES, TRAPS)


def parse(**changes: str) -> None:
    names = ("classes", "items", "monsters", "statuses", "abilities", "traps")
    texts = dict(zip(names, GOOD, strict=True))
    for key, (old, new) in changes.items():
        texts[key] = texts[key].replace(old, new) if old else new
    parse_gamedata(*(texts[n] for n in names))


def test_shipped_fighter_matches_gdd_6_2_and_6_4() -> None:
    fighter = load_gamedata().classes["fighter"]
    assert (fighter.strength, fighter.dexterity) == (16, 10)
    assert fighter.rank_hp == (30, 35, 35, 40, 45)
    assert fighter.rank_atk == (0, 1, 1, 1, 1) and fighter.rank_dmg == (0, 0, 0, 1, 1)
    assert fighter.signature == "stubborn"
    assert (fighter.weapon, fighter.offhand, fighter.head, fighter.body) == (
        "company_pickaxe", "sheet_metal_shield", "hard_hat", "boiler_suit",
    )  # fmt: skip


def test_shipped_items_match_gdd_8_1() -> None:
    items = load_gamedata().items
    pick = items.weapons["company_pickaxe"]
    assert (pick.dice_n, pick.dice_sides, pick.stat, pick.cost) == (1, 8, "str", 100)
    suit = items.armor["boiler_suit"]
    assert (suit.weight, suit.dr, suit.defense, suit.dur, suit.repair_rate) == (
        "heavy",
        2,
        0,
        18,
        2,  # the GDD said 3; retuned in M9 (A84)
    )
    assert items.shields["sheet_metal_shield"].defense == 1
    assert items.hats["hard_hat"].defense == 0


def test_shipped_weapons_match_gdd_8_1() -> None:
    w = load_gamedata().items.weapons
    # key: (tier, dice, stat, atk, dmg, cost, two_handed, light, noise, stuns)
    want = {
        "company_pickaxe": (1, (1, 8), "str", 0, 0, 100, 0, 0, 0, 0),
        "box_cutter": (1, (1, 6), "finesse", 0, 0, 100, 0, 1, 0, 0),
        "hatchet": (1, (1, 6), "str", 0, 0, 100, 0, 1, 0, 0),
        "prybar": (1, (1, 6), "str", 1, 0, 100, 0, 0, 0, 0),
        "utility_knife": (1, (1, 4), "finesse", 0, 0, 100, 0, 1, 0, 0),
        "gravediggers_shovel": (2, (1, 8), "str", 0, 0, 100, 0, 0, 8, 1),
        "surveyors_pick": (2, (1, 8), "finesse", 0, 0, 100, 0, 0, 0, 0),
        "sledgehammer": (2, (1, 12), "str", 0, 0, 130, 1, 0, 8, 1),
        "foremans_pickaxe": (3, (1, 10), "str", 1, 0, 100, 0, 0, 0, 0),
        "assay_blade": (3, (1, 8), "finesse", 0, 1, 100, 0, 0, 0, 0),
    }  # fmt: skip
    assert set(w) == set(want)
    for key, row in want.items():
        d = w[key]
        got = (d.tier, (d.dice_n, d.dice_sides), d.stat, d.atk, d.dmg, d.cost, d.two_handed,
               d.light, d.noise, d.stuns)  # fmt: skip
        assert got == row, key


def test_shipped_armor_matches_gdd_8_1() -> None:
    a = load_gamedata().items.armor
    want = {  # key: (tier, weight, DR, DEF, Dur, repair rate)
        "hi_vis_vest": (1, "light", 0, 2, 10, 1),
        "ballistic_vest": (2, "light", 1, 2, 12, 2),
        "padded_coveralls": (1, "medium", 1, 1, 14, 2),
        "welders_jacket": (2, "medium", 2, 1, 16, 3),
        "boiler_suit": (1, "heavy", 2, 0, 18, 2),
        "miners_plate": (2, "heavy", 3, -1, 20, 4),
    }  # fmt: skip
    assert set(a) == set(want)
    for key, row in want.items():
        d = a[key]
        assert (d.tier, d.weight, d.dr, d.defense, d.dur, d.repair_rate) == row, key


def test_shipped_shields_hats_and_trinkets_match_gdd_8_1() -> None:
    items = load_gamedata().items
    assert {k: v.defense for k, v in items.shields.items()} == {
        "sheet_metal_shield": 1, "riot_shield": 2,
    }  # fmt: skip
    assert {k: (v.defense, v.lamp) for k, v in items.hats.items()} == {
        "hard_hat": (0, 4), "reinforced_hard_hat": (1, 4), "headlamp_hard_hat": (0, 5),
    }  # fmt: skip
    assert {k: (v.atk, v.hp, v.waives) for k, v in items.trinkets.items()} == {
        "laminated_lanyard": (0, 0, 1), "company_challenge_coin": (1, 0, 0), "thermos": (0, 3, 0),
    }  # fmt: skip


def test_shipped_consumables_match_gdd_8_2() -> None:
    c = load_gamedata().items.consumables
    want = {  # key: (list price, carry limit, effect, value, status)
        "patch_up_kit": (5, 4, "heal", 10, ""), "torch": (2, 3, "light", 40000, ""),
        "overtime_fizz": (7, 2, "status", 800, "overtime"),
        "sanctified_detergent": (6, 2, "status", 5000, "detergent"),
    }  # fmt: skip
    assert set(c) == set(want)
    for key, row in want.items():
        d = c[key]
        assert (d.price, d.carry, d.effect, d.value, d.status) == row, key


def test_found_stock_bills_half_the_list_price_rounded_up() -> None:
    c = load_gamedata().items.consumables
    assert {k: found_charge(v) for k, v in c.items()} == {
        "patch_up_kit": 3, "torch": 1, "overtime_fizz": 4, "sanctified_detergent": 3,
    }  # fmt: skip


def test_shipped_valuables_match_gdd_8_3() -> None:
    v = load_gamedata().items.valuables
    assert {k: (d.credit, d.weight) for k, d in v.items()} == {
        "silver_nugget": (2, 50), "rough_gem": (4, 30), "silver_ingot": (6, 12), "cut_gem": (9, 8),
    }  # fmt: skip


def test_every_item_id_belongs_to_exactly_one_category() -> None:
    items = load_gamedata().items
    assert items.category("hatchet") == "weapon" and items.category("torch") == "consumable"
    assert items.category("rough_gem") == "valuable" and items.category("thermos") == "trinket"
    with pytest.raises(KeyError):
        items.category("nonesuch")


def test_item_ids_may_not_repeat_across_categories() -> None:
    with pytest.raises(DataError, match="duplicate"):
        parse(items=("[valuable.nugget]", "[valuable.pick]"))


def test_item_flags_and_enums_are_checked() -> None:
    with pytest.raises(DataError, match="effect"):
        parse(items=('effect = "heal"', 'effect = "explode"'))
    with pytest.raises(DataError, match="light"):
        parse(items=("light = 0", "light = 2"))
    with pytest.raises(DataError, match="tier"):
        parse(items=("tier = 1\nlight", "tier = 4\nlight"))
    with pytest.raises(DataError, match="two-handed"):
        parse(items=("two_handed = 0\ntier = 1\nlight = 0", "two_handed = 1\ntier = 1\nlight = 1"))


def test_a_status_consumable_names_a_status_that_exists() -> None:
    with pytest.raises(DataError, match="nonesuch"):
        parse(items=('status = "stunned"', 'status = "nonesuch"'))


def test_a_heal_or_light_consumable_names_no_status() -> None:
    with pytest.raises(DataError, match="status"):
        parse(
            items=(
                'effect = "heal"\nvalue = 10\nstatus = ""',
                'effect = "heal"\nvalue = 10\nstatus = "stunned"',
            )
        )


def test_shipped_miner_matches_gdd_7_6() -> None:
    miner = load_gamedata().monsters["shambling_miner"]
    assert (miner.hp, miner.atk, miner.defense, miner.dr) == (12, 2, 0, 0)
    assert (miner.dice_n, miner.dice_sides, miner.dmg) == (1, 6, 1)
    assert (miner.move_cost, miner.attack_cost, miner.sight, miner.threat) == (150, 100, 5, 3)
    assert miner.faction == "undead"


def test_shipped_rogue_and_ranger_match_gdd_6_2_and_6_3() -> None:
    classes = load_gamedata().classes
    rogue, ranger = classes["rogue"], classes["ranger"]
    assert (rogue.strength, rogue.dexterity, rogue.rank_hp) == (10, 16, (22, 26, 26, 30, 34))
    assert (ranger.strength, ranger.dexterity, ranger.rank_hp) == (13, 13, (26, 30, 30, 34, 38))
    assert (rogue.weapon, rogue.offhand, rogue.body) == ("box_cutter", "", "hi_vis_vest")
    assert (ranger.weapon, ranger.offhand, ranger.body) == (
        "hatchet",
        "hatchet",
        "padded_coveralls",
    )
    assert [classes[c].signature for c in ("fighter", "rogue", "ranger")] == [
        "stubborn", "backstab", "tracker",
    ]  # fmt: skip
    assert [classes[c].ability for c in ("fighter", "rogue", "ranger")] == [
        "cleave", "poison_blades", "dual_strike",
    ]  # fmt: skip


def test_shipped_kit_items_match_gdd_8_1() -> None:
    items = load_gamedata().items
    cutter, hatchet = items.weapons["box_cutter"], items.weapons["hatchet"]
    assert (cutter.dice_sides, cutter.stat) == (6, "finesse")
    assert (hatchet.dice_sides, hatchet.stat) == (6, "str")
    vest, coveralls = items.armor["hi_vis_vest"], items.armor["padded_coveralls"]
    assert (vest.weight, vest.dr, vest.defense, vest.dur, vest.repair_rate) == (
        "light",
        0,
        2,
        10,
        1,
    )
    assert (coveralls.weight, coveralls.dr, coveralls.defense, coveralls.dur) == (
        "medium",
        1,
        1,
        14,
    )


def test_shipped_cave_vermin_matches_gdd_7_6() -> None:
    vermin = load_gamedata().monsters["cave_vermin"]
    assert (vermin.hp, vermin.atk, vermin.defense, vermin.dr) == (6, 1, 2, 0)
    assert (vermin.dice_n, vermin.dice_sides, vermin.dmg) == (1, 3, 0)
    assert (vermin.move_cost, vermin.attack_cost, vermin.sight, vermin.faction) == (
        50,
        100,
        6,
        "beast",
    )


def test_shipped_abilities_match_gdd_6_6() -> None:
    abilities = load_gamedata().abilities
    cleave, poison, dual = abilities["cleave"], abilities["poison_blades"], abilities["dual_strike"]
    assert (cleave.kind, cleave.unlock_rank, cleave.cooldown_ticks, cleave.cooldown_ticks_up) == (
        "cleave",
        3,
        400,
        300,
    )
    assert (cleave.value, cleave.value_up) == (2, 0)  # -2 ATK per attack, none at Rank 5
    assert (poison.kind, poison.cooldown_ticks, poison.value, poison.value_up) == (
        "coat",
        3000,
        2,
        3,
    )
    assert (poison.charges, poison.charges_up) == (5, 6)
    assert (dual.kind, dual.cooldown_ticks, dual.cooldown_ticks_up) == ("dual_strike", 500, 300)
    assert (dual.value, dual.value_up) == (1, 2)
    assert all(a.unlock_rank == 3 for a in abilities.values())


def test_shipped_soaked_matches_gdd_7_5() -> None:
    soaked = load_gamedata().statuses["soaked"]
    assert (soaked.duration_ticks, soaked.defense) == (200, -1)


def test_shipped_poison_statuses_match_gdd_7_5() -> None:
    statuses = load_gamedata().statuses
    assert (statuses["poisoned"].duration_ticks, statuses["poisoned"].tick_ticks) == (500, 100)
    assert statuses["coated"].duration_ticks == 0  # until the charges are spent


def test_shipped_test_trap_matches_gdd_9_7() -> None:
    spring = load_gamedata().traps["spring_trap"]
    assert (spring.dice_n, spring.dice_sides, spring.dmg, spring.effect) == (1, 6, 2, "damage")


def test_class_must_reference_an_ability_that_exists() -> None:
    with pytest.raises(DataError, match="nonesuch"):
        parse(classes=('ability = "cleave"', 'ability = "nonesuch"'))


def test_ability_kind_and_unlock_rank_are_checked() -> None:
    with pytest.raises(DataError, match="kind"):
        parse(abilities=('kind = "cleave"', 'kind = "fireball"'))
    with pytest.raises(DataError, match="unlock_rank"):
        parse(abilities=("unlock_rank = 3", "unlock_rank = 9"))


def test_shipped_statuses_match_gdd_7_5() -> None:
    statuses = load_gamedata().statuses
    stun = statuses["stunned"]
    assert (stun.delay_ticks, stun.immune_ticks, stun.cost_pct) == (100, 300, 100)
    assert statuses["overtime"].cost_pct == 60


def test_well_formed_text_parses() -> None:
    parse()


@pytest.mark.parametrize(
    ("table", "old", "new"),
    [
        ("classes", "strength = 16", "strength = 16.5"),
        ("items", "dice_sides = 8", "dice_sides = true"),
        ("monsters", "hp = 12", "hp = 12.0"),
        ("statuses", "cost_pct = 100", "cost_pct = 1e2"),
    ],
)
def test_floats_and_bools_are_rejected(table: str, old: str, new: str) -> None:
    with pytest.raises(DataError, match="integer"):
        parse(**{table: (old, new)})


@pytest.mark.parametrize(
    ("table", "old", "new", "word"),
    [
        ("classes", 'name = "Fighter"\n', 'name = "Fighter"\nbonus = 1\n', "unknown"),
        ("classes", "strength = 16\n", "", "missing"),
        ("monsters", "threat = 3\n", "", "missing"),
        ("statuses", "delay_ticks = 100\n", "delay_ticks = 100\nmystery = 1\n", "unknown"),
    ],
)
def test_unknown_and_missing_keys_are_rejected(table: str, old: str, new: str, word: str) -> None:
    with pytest.raises(DataError, match=word):
        parse(**{table: (old, new)})


def test_bad_enumerated_values_are_rejected() -> None:
    with pytest.raises(DataError, match="stat"):
        parse(items=('stat = "str"', 'stat = "magic"'))
    with pytest.raises(DataError, match="weight"):
        parse(items=('weight = "heavy"', 'weight = "gigantic"'))
    with pytest.raises(DataError, match="faction"):
        parse(monsters=('faction = "undead"', 'faction = "robot"'))


def test_class_must_reference_items_that_exist() -> None:
    with pytest.raises(DataError, match="nonesuch"):
        parse(classes=('weapon = "pick"', 'weapon = "nonesuch"'))
    with pytest.raises(DataError, match="nonesuch"):
        parse(classes=('body = "suit"', 'body = "nonesuch"'))


def test_rank_tables_need_exactly_five_integers() -> None:
    with pytest.raises(DataError, match="rank_hp"):
        parse(classes=("[30, 35, 35, 40, 45]", "[30, 35, 35]"))
    with pytest.raises(DataError, match="integer"):
        parse(classes=("[30, 35, 35, 40, 45]", "[30, 35, 35, 40, 45.5]"))


def test_class_blurbs_fit_one_line_of_the_select_screen() -> None:
    assert all(len(c.blurb) <= 65 for c in load_gamedata().classes.values())


# (hp, atk, def, dice, flat, dr, move, attack, sight, threat, behavior,
#  min level, weight, grave weight)
GDD_ROSTER = {
    "shambling_miner": (12, 2, 0, (1, 6), 1, 0, 150, 100, 5, 3, "hunter", 1, 15, 30),
    "gravedigger_skeleton": (20, 3, 2, (1, 8), 0, 1, 100, 100, 7, 5, "skeleton", 2, 8, 20),
    "timecard_wraith": (14, 4, 4, (1, 4), 0, 0, 100, 100, 6, 6, "phaser", 3, 5, 14),
    "cave_vermin": (6, 1, 2, (1, 3), 0, 0, 50, 100, 6, 3, "swarm", 1, 25, 10),
    "blind_ore_eel": (18, 4, 1, (1, 6), 2, 0, 100, 100, 2, 4, "eel", 1, 20, 8),
    "gem_badger": (16, 3, 2, (1, 6), 1, 0, 80, 100, 6, 3, "badger", 1, 20, 8),
    "foreman_grimsby": (40, 4, 2, (1, 8), 2, 1, 100, 100, 9, 0, "overseer", 1, 0, 0),
    "prospector_vane": (32, 4, 4, (1, 6), 1, 0, 100, 100, 9, 0, "trapper", 1, 0, 0),
}


def test_the_whole_roster_matches_gdd_7_6_and_9_4() -> None:
    monsters = load_gamedata().monsters
    assert set(monsters) == set(GDD_ROSTER)
    for kind, want in GDD_ROSTER.items():
        m = monsters[kind]
        got = (
            (m.hp, m.atk, m.defense, (m.dice_n, m.dice_sides), m.dmg, m.dr)
            + (m.move_cost, m.attack_cost, m.sight, m.threat, m.behavior)
            + (m.min_level, m.weight, m.grave_weight)
        )
        assert got == want, kind


def test_factions_follow_the_gdd() -> None:
    monsters = load_gamedata().monsters
    undead = {k for k, m in monsters.items() if m.faction == "undead"}
    beasts = {k for k, m in monsters.items() if m.faction == "beast"}
    humans = {k for k, m in monsters.items() if m.faction == "human"}
    assert undead == {"shambling_miner", "gravedigger_skeleton", "timecard_wraith"}
    assert beasts == {"cave_vermin", "blind_ore_eel", "gem_badger"}
    assert humans == {"foreman_grimsby", "prospector_vane"}


def test_unknown_behaviors_are_rejected() -> None:
    with pytest.raises(DataError, match="behavior"):
        parse(monsters=('behavior = "hunter"', 'behavior = "sulker"'))


def test_all_three_traps_match_gdd_9_7() -> None:
    traps = load_gamedata().traps
    assert list(traps) == [
        "spring_trap",
        "tripwire_charge",
        "stun_charge",
    ]  # the order dice pick in
    tripwire, stun = traps["tripwire_charge"], traps["stun_charge"]
    assert (tripwire.dice_n, tripwire.dice_sides, tripwire.dmg, tripwire.effect) == (
        2,
        4,
        0,
        "damage",
    )
    assert stun.effect == "stun"


def test_every_hard_hat_takes_two_off_trap_damage() -> None:
    hats = load_gamedata().items.hats
    assert hats["hard_hat"].trap_reduction == 2


def test_unknown_trap_effects_are_rejected() -> None:
    with pytest.raises(DataError, match="effect"):
        parse(traps=('effect = "damage"', 'effect = "explode"'))
