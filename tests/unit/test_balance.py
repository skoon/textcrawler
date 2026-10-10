import pytest

from minetoofar.content.balance import BalanceError, load_balance, parse_balance

GOOD = """
[layout]
width = 80
height = 40
leaf_min_w = 12
leaf_min_h = 9
max_depth = 5
early_stop_from_depth = 3
early_stop_pct = 15
split_long_axis_pct = 75
room_margin = 2
room_min = 5
room_max_w = 24
room_max_h = 12
cave_fill_pct = 35
cave_iterations = 3
cave_wall_neighbors = 5
cave_min_pct = 30
cave_tries = 4
door_pct = 60
rooms_min = 8
rooms_max = 14
max_attempts = 20
extra_links_base = 1
extra_links_level_div = 2

[play]
hard_hat_radius = 4
torch_radius = 8
move_cost = 100
door_cost = 100
wait_cost = 100
use_cost = 100
grave_fall_sides = 4
grave_climb_ticks = 200
torch_brine_one_in = 2
torch_crit_one_in = 4

[combat]
flank_bonus = 2
beast_bonus = 2
backstab_dice = 2
backstab_sides = 4
tracker_radius_sq = 25
spot_radius_sq = 9
passive_spot_one_in = 3

[ai]
wake_noise_one_in = 2
buried_rise_radius_sq = 9
eel_resubmerge_ticks = 200
eel_ambush_bonus = 4
badger_flee_pct = 40
badger_burrow_ticks = 1200
clock_in_pct = 35
phaser_wall_defense = 4
swarm_max = 3
aura_radius_sq = 25
aura_ticks = 300
overseer_min = 2
overseer_max = 3
trap_interval_ticks = 600
trap_sight_sq = 36
trapper_max_traps = 4
trapper_flee_ticks = 300
speech_hit_cooldown = 500

[noise]
melee = 5
door = 3
clang = 8

[theme]
graveyard_pct = 30
grimsby_pct = 50

[features]
flood_min_pct = 30
level3_flooded_min = 2
level3_flooded_max = 3
collapse_pct = 50
bunk_pct = 20
rubble_pct = 25
cemetery_pct = 50
gravestone_pct = 12
grave_pct = 6
monuments = 2

[humans]
distance_pct = 50
last_level_distance_pct = 75
tic_one_in = 3
camp_traps = 2

[spawns]
budget_base = 10
budget_per_level = 4
graveyard_budget_pct = 125
min_entry_distance = 80
room_cap = 6
asleep_pct = 35
bunk_asleep_pct = 80
grave_buried_pct = 50
pack_min = 3
pack_max = 5

[levels]
cavern_pct = [0, 20, 40, 60, 90]
trap_counts = [2, 3, 4, 5, 6]
"""


def test_shipped_balance_matches_gdd_numbers() -> None:
    b = load_balance()
    assert (b.layout.width, b.layout.height) == (80, 40)
    assert b.cavern_pct == (0, 20, 40, 60, 90)
    assert b.layout.rooms_min == 8 and b.layout.rooms_max == 14
    assert (b.layout.room_max_w, b.layout.room_max_h) == (24, 12)


def test_shipped_play_numbers_match_gdd() -> None:
    play = load_balance().play
    assert (play.hard_hat_radius, play.torch_radius) == (4, 8)
    assert (play.move_cost, play.door_cost, play.wait_cost, play.use_cost) == (100, 100, 100, 100)


def test_shipped_spawn_numbers_match_gdd_9() -> None:
    spawns = load_balance().spawns
    assert (spawns.budget_base, spawns.budget_per_level) == (10, 4)  # budget 10 + 4*L
    assert (spawns.room_cap, spawns.asleep_pct, spawns.bunk_asleep_pct) == (6, 35, 80)
    assert spawns.graveyard_budget_pct == 125 and (spawns.pack_min, spawns.pack_max) == (3, 5)
    assert spawns.min_entry_distance == 80  # 8 straight steps at 10 per step


def test_shipped_combat_numbers_match_the_gdd() -> None:
    c = load_balance().combat
    assert c.flank_bonus == 2  # 7.4
    assert (c.backstab_dice, c.backstab_sides) == (2, 4)  # 6.5: +2d4
    assert c.beast_bonus == 2 and c.tracker_radius_sq == 25  # 6.5: radius 5
    assert c.spot_radius_sq == 9 and c.passive_spot_one_in == 3  # 6.5 and 9.7


def test_shipped_ai_numbers_match_gdd_7_6_and_7_7() -> None:
    ai = load_balance().ai
    assert (ai.eel_ambush_bonus, ai.eel_resubmerge_ticks) == (4, 200)  # +4 ATK; two turns
    assert (ai.badger_flee_pct, ai.badger_burrow_ticks) == (40, 1200)  # 40% HP; 12 turns
    assert ai.clock_in_pct == 35 and ai.swarm_max == 3 and ai.phaser_wall_defense == 4
    assert (ai.aura_radius_sq, ai.aura_ticks) == (25, 300)  # within 5 tiles; 300 ticks
    assert (ai.overseer_min, ai.overseer_max) == (2, 3)  # Grimsby keeps distance 2-3
    assert (ai.trap_interval_ticks, ai.trap_sight_sq, ai.trapper_max_traps) == (600, 36, 4)
    assert ai.wake_noise_one_in == 2 and ai.buried_rise_radius_sq == 9


def test_shipped_noise_radii_match_gdd_7_7() -> None:
    noise = load_balance().noise
    assert (noise.melee, noise.door, noise.clang) == (5, 3, 8)


def test_ai_and_noise_sections_are_required() -> None:
    with pytest.raises(BalanceError, match="ai"):
        parse_balance(GOOD.replace("eel_ambush_bonus = 4\n", ""))
    with pytest.raises(BalanceError, match="noise"):
        parse_balance(GOOD.replace("clang = 8\n", ""))


def test_combat_section_is_required() -> None:
    with pytest.raises(BalanceError, match="combat"):
        parse_balance(GOOD.replace("flank_bonus = 2\n", ""))


def test_shipped_generation_numbers_match_the_gdd() -> None:
    b = load_balance()
    assert b.theme.graveyard_pct == 30 and b.theme.grimsby_pct == 50  # 9.4, 9.6
    assert (b.humans.distance_pct, b.humans.last_level_distance_pct) == (50, 75)
    assert (b.features.flood_min_pct, b.features.level3_flooded_max) == (30, 3)
    assert b.trap_counts == (2, 3, 4, 5, 6)  # 9.1


def test_trap_counts_cover_five_levels() -> None:
    with pytest.raises(BalanceError, match="trap_counts"):
        parse_balance(GOOD.replace("[2, 3, 4, 5, 6]", "[2, 3]"))


@pytest.mark.parametrize("section", ["theme", "features", "humans"])
def test_the_new_generation_sections_are_required(section: str) -> None:
    key = {"theme": "graveyard_pct", "features": "flood_min_pct", "humans": "camp_traps"}[section]
    text = "\n".join(line for line in GOOD.splitlines() if not line.startswith(key))
    with pytest.raises(BalanceError, match=section):
        parse_balance(text)


def test_spawns_section_is_required() -> None:
    with pytest.raises(BalanceError, match="spawns"):
        parse_balance(GOOD.replace("room_cap = 6\n", ""))


def test_shipped_terrain_numbers_match_the_gdd() -> None:
    play = load_balance().play
    assert (play.grave_fall_sides, play.grave_climb_ticks) == (4, 200)  # 5.4: 1d4, two turns
    assert (play.torch_brine_one_in, play.torch_crit_one_in) == (2, 4)  # 8.6: 50% and 25%


def test_play_section_is_required_and_integer_only() -> None:
    with pytest.raises(BalanceError, match="play"):
        parse_balance(GOOD.replace("torch_radius = 8\n", ""))
    with pytest.raises(BalanceError, match="integer"):
        parse_balance(GOOD.replace("torch_radius = 8", "torch_radius = 8.5"))
    with pytest.raises(BalanceError, match="unknown"):
        parse_balance(GOOD.replace("use_cost = 100", "use_cost = 100\nmystery = 1"))


def test_parse_accepts_well_formed_text() -> None:
    assert parse_balance(GOOD).layout.max_attempts == 20


def test_floats_are_rejected() -> None:
    with pytest.raises(BalanceError, match="integer"):
        parse_balance(GOOD.replace("door_pct = 60", "door_pct = 60.5"))


def test_booleans_are_rejected() -> None:
    with pytest.raises(BalanceError, match="integer"):
        parse_balance(GOOD.replace("door_pct = 60", "door_pct = true"))


def test_unknown_key_is_rejected() -> None:
    with pytest.raises(BalanceError, match="unknown"):
        parse_balance(GOOD.replace("[levels]", "mystery = 1\n[levels]"))


def test_missing_key_is_rejected() -> None:
    with pytest.raises(BalanceError, match="missing"):
        parse_balance(GOOD.replace("door_pct = 60\n", ""))


def test_cavern_list_must_cover_five_levels_of_integers() -> None:
    with pytest.raises(BalanceError):
        parse_balance(GOOD.replace("[0, 20, 40, 60, 90]", "[0, 20, 40]"))
    with pytest.raises(BalanceError, match="integer"):
        parse_balance(GOOD.replace("[0, 20, 40, 60, 90]", "[0, 20, 40, 60, 90.5]"))
