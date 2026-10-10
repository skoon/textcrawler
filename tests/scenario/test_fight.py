"""Combat, the scheduler, and monster behaviour on hand-drawn maps with scripted dice."""

import pytest

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.core.rng import Rng
from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import (
    ArmorDamaged,
    Attacked,
    Blocked,
    BlockReason,
    DoorOpened,
    Killed,
    Move,
    Noticed,
    PlayerDied,
    RankSet,
    Run,
    SetRank,
    Spotted,
    StubbornInvoked,
    Wait,
    Waited,
)
from minetoofar.sim.game import Game, GameOver
from minetoofar.sim.statuses import apply_status
from tests.helpers import DATA, MINER, ScriptedRng, make_game

CELL = ["####", "#<.#", "####"]  # the player at (1,1), one free tile beside them
HALL = ["############", "#<.........#", "############"]
E = Move(1, 0)


def face(n: int) -> int:
    """The scripted below() value that yields face n of a die."""
    return n - 1


def hunting_pair(script: list[int], rank: int = 1) -> Game:
    return make_game(CELL, [(MINER, (2, 1), "hunting")], ScriptedRng(script), rank)


# -- the player attacks --------------------------------------------------------------------


def test_bump_attack_hits_wakes_the_sleeper_and_provokes_a_reply() -> None:
    rng = ScriptedRng([face(15), face(5), face(1)])  # player hits for 5+3; the Miner rolls a 1
    g = make_game(CELL, [(MINER, (2, 1), "asleep")], rng)
    events = g.submit(E)
    assert events == [
        Attacked(0, "Hale", 1, "Shambling Miner", 15, Outcome.HIT, 8),
        Noticed(1, "Shambling Miner"),
        Attacked(1, "Shambling Miner", 0, "Hale", 1, Outcome.MISS, 0),
    ]
    assert g.monsters[0].hp == 4 and g.monsters[0].state == "hunting"
    assert g.pos == Pos(1, 1) and g.ticks == 100
    assert rng.queue == []


def test_a_kill_removes_the_monster() -> None:
    g = make_game(CELL, [(MINER, (2, 1), "idle")], ScriptedRng([face(15), face(5)]))
    g.monsters[0].hp = 8
    assert g.submit(E) == [
        Attacked(0, "Hale", 1, "Shambling Miner", 15, Outcome.HIT, 8),
        Killed(1, "Shambling Miner"),
    ]
    assert g.monsters == []


def test_a_natural_one_misses_and_a_natural_twenty_doubles_the_dice() -> None:
    # miss; the Miner stirs and swings (a 1); then a critical with two d8 kills it
    rng = ScriptedRng([face(1), face(1), face(20), face(8), face(8)])
    g = make_game(CELL, [(MINER, (2, 1), "idle")], rng)
    miss = g.submit(E)[0]
    crit = g.submit(E)
    assert isinstance(miss, Attacked) and miss.outcome is Outcome.MISS and miss.damage == 0
    assert isinstance(crit[0], Attacked) and crit[0].outcome is Outcome.CRIT
    assert crit[0].damage == 8 + 8 + 3  # two d8 plus the flat bonus
    assert rng.queue == []


def test_pickaxe_costs_one_turn_and_leaves_the_player_in_place() -> None:
    g = make_game(CELL, [(MINER, (2, 1), "idle")], ScriptedRng([face(1), face(1)]))
    g.submit(E)
    assert g.ticks == 100 and g.pos == Pos(1, 1)


def test_attacks_cannot_cut_corners() -> None:
    g = make_game(["#####", "#<#.#", "#..##", "#####"], [(MINER, (2, 2), "idle")])
    assert g.submit(Move(1, 1)) == [Blocked(Pos(2, 2), BlockReason.CORNER)]  # (2,1) is wall
    assert g.ticks == 0


# -- monsters attack the player ------------------------------------------------------------


def test_a_miner_hit_is_reduced_by_dr_and_wears_the_armor() -> None:
    g = hunting_pair([face(15), face(4)])
    events = g.submit(Wait())
    assert events[1:] == [
        Attacked(1, "Shambling Miner", 0, "Hale", 15, Outcome.HIT, 4 + 1 - 2),
        ArmorDamaged("Boiler Suit", 17, 18, False),
    ]
    assert (g.player.hp, g.player.body_dur) == (27, 17)


def test_a_critical_costs_two_durability_and_doubles_the_dice() -> None:
    g = hunting_pair([face(20), face(4), face(6)])
    g.submit(Wait())
    assert g.player.hp == 30 - (4 + 6 + 1 - 2) and g.player.body_dur == 16


def test_damage_reduction_never_goes_below_one() -> None:
    g = hunting_pair([face(15), face(1)])  # 1 + 1 - DR 2 -> 0 -> 1
    g.submit(Wait())
    assert g.player.hp == 29


def test_broken_armor_stops_absorbing() -> None:
    g = hunting_pair([face(15), face(4), face(15), face(4)])
    g.player.body_dur = 1
    events = g.submit(Wait())
    assert ArmorDamaged("Boiler Suit", 0, 18, True) in events
    g.submit(Wait())
    assert g.player.hp == 30 - 3 - 5  # the second hit has no DR to subtract


def test_a_miner_swing_that_misses_changes_nothing() -> None:
    g = hunting_pair([face(1)])
    events = g.submit(Wait())
    assert events[1:] == [Attacked(1, "Shambling Miner", 0, "Hale", 1, Outcome.MISS, 0)]
    assert (g.player.hp, g.player.body_dur) == (30, 18)


def test_level_five_miners_hit_harder() -> None:
    g = make_game(CELL, [(MINER, (2, 1), "hunting")], ScriptedRng([face(15), face(4)]), level=5)
    g.submit(Wait())
    assert g.player.hp == 30 - (4 + 3 - 2)  # 1d6+3 at level 5, then DR 2


# -- Stubborn and death --------------------------------------------------------------------


def test_stubborn_saves_the_fighter_once_then_the_next_blow_kills() -> None:
    g = hunting_pair([face(15), face(4), face(15), face(1)])
    g.player.hp = 3
    first = g.submit(Wait())
    assert StubbornInvoked() in first and g.player.hp == 1 and not g.dead
    assert g.player.stubborn_used
    second = g.submit(Wait())
    assert PlayerDied("Shambling Miner") in second
    assert g.dead and g.cause == "Shambling Miner" and g.player.hp == 0


def test_armor_wears_even_on_the_blow_stubborn_absorbs() -> None:
    g = hunting_pair([face(15), face(6)])
    g.player.hp = 2
    events = g.submit(Wait())
    kinds = [type(e) for e in events]
    assert kinds.index(ArmorDamaged) < kinds.index(StubbornInvoked)  # 7.2 step 6 order


def test_dead_players_cannot_act_and_monsters_stop() -> None:
    g = hunting_pair([face(15), face(1)])
    g.player.hp, g.player.stubborn_used = 1, True
    g.submit(Wait())
    assert g.dead
    with pytest.raises(GameOver):
        g.submit(Wait())


def test_no_monster_acts_after_the_player_dies() -> None:
    rows = ["#####", "#<..#", "#####"]
    g = make_game(rows, [(MINER, (2, 1), "hunting")], ScriptedRng([face(15), face(1)]))
    g.player.hp, g.player.stubborn_used = 1, True
    g.monsters.append(
        g.monsters[0].__class__(**{**g.monsters[0].__dict__, "id": 2, "pos": Pos(3, 1)})
    )
    events = g.submit(Wait())
    assert sum(isinstance(e, Attacked) for e in events) == 1  # the second Miner never gets a turn


# -- the scheduler -------------------------------------------------------------------------


def test_ties_go_to_the_player_first() -> None:
    g = hunting_pair([face(1), face(1)])
    g.submit(Wait())  # the Miner acts once: its ready_at 0 < 100
    assert g.monsters[0].ready_at == 100 == g.player.ready_at
    events = g.submit(Wait())  # now it acts at 100 < 200
    assert sum(isinstance(e, Attacked) for e in events) == 1


def test_lower_id_acts_first_at_equal_ready_at() -> None:
    rows = ["#####", "#.<.#", "#####"]
    script = ScriptedRng([face(1)] * 2)
    g = make_game(rows, [(MINER, (1, 1), "hunting"), (MINER, (3, 1), "hunting")], script)
    events = g.submit(Wait())
    attackers = [e.attacker for e in events if isinstance(e, Attacked)]
    assert attackers == [1, 2]


def test_a_miner_moves_every_one_and_a_half_turns() -> None:
    g = make_game(HALL, [(MINER, (8, 1), "hunting")])
    xs = []
    for _ in range(5):
        g.submit(Wait())
        xs.append(g.monsters[0].pos.x)
    # ready_at 0, 150, 300, 450, 600 versus the player's 100, 200, 300 (tie: player first), ...
    assert xs == [7, 6, 6, 5, 4]


def test_overtime_makes_the_players_actions_cost_sixty_percent() -> None:
    g = make_game(HALL)
    apply_status(g.player, "overtime", now=0, defs=DATA.statuses)
    g.submit(Wait())
    g.submit(E)
    assert g.ticks == 60 + 60


def test_overtime_speeds_a_miners_walk_to_ninety_ticks() -> None:
    g = make_game(HALL, [(MINER, (9, 1), "hunting")])
    apply_status(g.monsters[0], "overtime", now=0, defs=DATA.statuses)
    g.submit(Wait())  # steps at 0 and again at 90 (both before the player's 100)
    assert g.monsters[0].pos == Pos(7, 1) and g.monsters[0].ready_at == 180


def test_stun_costs_a_monster_one_turn_and_then_it_is_immune_for_three() -> None:
    g = make_game(HALL, [(MINER, (8, 1), "hunting")])
    miner = g.monsters[0]
    assert apply_status(miner, "stunned", now=0, defs=DATA.statuses) is True
    g.submit(Wait())  # the Miner would have moved at 0; stunned, its turn is at 100 (a tie)
    assert miner.pos == Pos(8, 1)
    g.submit(Wait())
    assert miner.pos == Pos(7, 1)
    assert apply_status(miner, "stunned", now=200, defs=DATA.statuses) is False  # immune to 400


# -- hunting -------------------------------------------------------------------------------


def test_hunters_walk_around_walls_toward_the_player() -> None:
    rows = [
        "#########",
        "#<..#...#",
        "#...#...#",
        "#.......#",
        "#########",
    ]
    g = make_game(rows, [(MINER, (7, 1), "hunting")], ScriptedRng([face(1)] * 20))
    for _ in range(12):
        g.submit(Wait())
        if g.monsters[0].pos.x <= 3:
            break
    assert g.monsters[0].pos.x <= 3  # it found the gap in the wall along the bottom row


def test_hunters_do_not_stack_on_each_other() -> None:
    g = make_game(HALL, [(MINER, (4, 1), "hunting"), (MINER, (5, 1), "hunting")])
    for _ in range(6):
        g.submit(Wait())
        assert len({m.pos for m in g.monsters}) == 2
        assert all(m.pos != g.player.pos for m in g.monsters)


def test_a_hunter_opens_doors_in_its_way() -> None:
    rows = ["#########", "#<...+..#", "#########"]
    g = make_game(rows, [(MINER, (7, 1), "hunting")])
    events = []
    for _ in range(4):
        events += g.submit(Wait())
    assert DoorOpened(Pos(5, 1), by=1) in events
    assert Tile(g.grid.get(5, 1)) == Tile.DOOR_OPEN
    assert g.monsters[0].pos.x <= 5


def test_a_monster_standing_in_a_doorway_cannot_strike_diagonally() -> None:
    rows = ["#####", "#.#/#", "#.<.#", "#####"]  # an open door at (3,1), diagonal to the player
    g = make_game(rows, [(MINER, (3, 1), "hunting")], ScriptedRng([face(1)] * 3))
    events = g.submit(Wait())
    assert not any(isinstance(e, Attacked) for e in events)
    assert g.monsters[0].pos == Pos(3, 2)  # it steps out squarely instead
    events = g.submit(Wait())
    assert any(isinstance(e, Attacked) for e in events)


# -- sleeping and idle monsters ------------------------------------------------------------


def test_a_sleeper_next_to_the_player_wakes_one_time_in_two() -> None:
    g = make_game(
        CELL, [(MINER, (2, 1), "asleep")], ScriptedRng([0, face(1)])
    )  # wake roll, then swing
    events = g.submit(Wait())
    assert events[1] == Noticed(1, "Shambling Miner") and g.monsters[0].state == "hunting"


def test_a_sleeper_that_stays_asleep_does_nothing() -> None:
    g = make_game(CELL, [(MINER, (2, 1), "asleep")], ScriptedRng([1]))  # below(2) == 1: no wake
    assert g.submit(Wait()) == [Waited()]
    assert g.monsters[0].state == "asleep" and g.monsters[0].ready_at == 100


def test_a_sleeper_within_four_tiles_wakes_one_time_in_six() -> None:
    g = make_game(HALL, [(MINER, (5, 1), "asleep")], ScriptedRng([0]))  # dx 4: d2 16 <= 16
    events = g.submit(Wait())
    assert Noticed(1, "Shambling Miner") in events
    g = make_game(HALL, [(MINER, (5, 1), "asleep")], ScriptedRng([3]))
    assert g.submit(Wait()) == [Waited()]
    assert g.monsters[0].state == "asleep"


def test_a_distant_sleeper_never_even_rolls() -> None:
    rng = ScriptedRng([])  # any draw would raise
    g = make_game(HALL, [(MINER, (9, 1), "asleep")], rng)
    for _ in range(3):
        g.submit(Wait())
    assert g.monsters[0].state == "asleep"


def test_an_idle_monster_notices_the_player_in_sight_and_closes_in() -> None:
    g = make_game(HALL, [(MINER, (6, 1), "idle")])  # dx 5 is exactly its sight
    events = g.submit(Wait())
    assert Noticed(1, "Shambling Miner") in events
    assert g.monsters[0].state == "hunting" and g.monsters[0].pos == Pos(5, 1)


def test_an_idle_monster_beyond_sight_or_behind_a_door_stays_put() -> None:
    g = make_game(HALL, [(MINER, (8, 1), "idle")])
    g.submit(Wait())
    assert g.monsters[0].state == "idle" and g.monsters[0].pos == Pos(8, 1)
    rows = ["#########", "#<.+....#", "#########"]
    g = make_game(rows, [(MINER, (4, 1), "idle")])  # dx 3 but a closed door between
    g.submit(Wait())
    assert g.monsters[0].state == "idle"


# -- seeing monsters, running, debug ------------------------------------------------------


def test_a_monster_entering_view_is_spotted_once() -> None:
    g = make_game(HALL, [(MINER, (8, 1), "asleep")], ScriptedRng([5, 5, 5]))  # no wake-ups
    spotted_at = []
    for step in range(1, 5):
        if any(isinstance(e, Spotted) for e in g.submit(E)):
            spotted_at.append(step)
    assert spotted_at == [3]  # at x=4 the Miner is four tiles off: inside the lamp's radius


def test_run_stops_as_soon_as_a_monster_is_in_view() -> None:
    rows = ["#" * 23, "#<" + "." * 20 + "#", "#" * 23]
    g = make_game(rows, [(MINER, (12, 1), "asleep")], ScriptedRng([5, 5, 5]))
    events = g.submit(Run(1, 0))
    assert g.pos == Pos(8, 1) and g.ticks == 700  # x=8: dx 4, the first tile that sees it
    assert events[-1] == Spotted(1, "Shambling Miner")


def test_run_stops_when_something_attacks() -> None:
    rows = ["#" * 23, "#<" + "." * 20 + "#", "#" * 23]
    g = make_game(rows, [(MINER, (3, 1), "hunting")], ScriptedRng([face(1)] * 10))
    events = g.submit(Run(1, 0))
    assert isinstance(events[-1], Attacked)
    assert g.pos == Pos(2, 1) and g.ticks == 100


def test_set_rank_changes_hp_and_stats_and_takes_no_time() -> None:
    g = make_game(CELL)
    g.player.hp = 5
    assert g.submit(SetRank(4)) == [RankSet(4)]
    view = g.view().hero
    assert (view.rank, view.hp, view.max_hp, view.atk) == (4, 40, 40, 6)
    assert g.ticks == 0
    with pytest.raises(ValueError):
        g.submit(SetRank(9))


def test_view_lists_only_visible_monsters() -> None:
    g = make_game(HALL, [(MINER, (3, 1), "idle"), (MINER, (10, 1), "idle")])
    assert [m.id for m in g.view().monsters] == [1]
    hero = g.view().hero
    assert (hero.name, hero.class_name, hero.hp, hero.defense, hero.damage) == (
        "Hale",
        "Fighter",
        30,
        1,
        "1d8+3",
    )
    assert (hero.body, hero.armor_dur, hero.armor_max) == ("Boiler Suit", 18, 18)


def test_games_with_the_same_seed_and_inputs_end_identically() -> None:
    def play() -> str:
        g = make_game(HALL, [(MINER, (6, 1), "idle")], Rng(99))
        for cmd in [Wait(), Wait(), E, E, Wait(), E]:
            if g.dead:
                break
            g.submit(cmd)
        return g.state_hash()

    assert play() == play()
