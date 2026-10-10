"""Facing, the rear arc, and flanking (GDD 7.4), plus the Rogue's Backstab (GDD 6.5)."""

from minetoofar.core.geometry import Pos
from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import Attacked, Killed, Move, Wait
from minetoofar.sim.game import Game
from minetoofar.sim.statuses import apply_status
from tests.helpers import DATA, MINER, ScriptedRng, inert, make_game

ROOM = ["#####", "#...#", "#.<.#", "#...#", "#####"]  # the player starts at (2, 2)
NORTH, SOUTH = (0, -1), (0, 1)


def face(n: int) -> int:
    return n - 1


def stunned(game: Game) -> Game:
    """Stun every monster so it cannot answer; Backstab-ignorant classes see a plain target."""
    for m in game.monsters:
        apply_status(m, "stunned", now=0, defs=DATA.statuses)
    return game


def attacked(events: list[object]) -> list[Attacked]:
    return [e for e in events if isinstance(e, Attacked)]


# -- facing ---------------------------------------------------------------------------------


def test_the_player_starts_facing_south_and_turns_with_each_move_and_attack() -> None:
    g = inert(make_game(ROOM, [(MINER, (3, 3), "hunting")], ScriptedRng([face(1)] * 6)))
    assert g.player.facing == SOUTH
    g.submit(Move(1, 0))
    assert g.player.facing == (1, 0)
    g.submit(Move(0, 1))  # the Miner stands south of (3, 2): attacking turns you toward it
    assert g.player.facing == SOUTH and g.pos == Pos(3, 2)


def test_a_refused_move_does_not_turn_the_player() -> None:
    g = make_game(ROOM)
    g.submit(Move(1, 0))
    assert g.player.facing == (1, 0)
    assert g.submit(Move(1, -1)) != []  # (4, 1) is a wall: refused
    assert g.player.facing == (1, 0) and g.pos == Pos(3, 2)


def test_a_walking_monster_faces_where_it_steps_and_an_attacker_faces_its_target() -> None:
    rows = ["#########", "#<......#", "#########"]
    g = make_game(rows, [(MINER, (6, 1), "hunting")], ScriptedRng([face(1)] * 8))
    g.submit(Wait())
    assert g.monsters[0].facing == (-1, 0)  # stepped west toward the player
    adj = make_game(ROOM, [(MINER, (2, 1), "hunting", (1, 0))], ScriptedRng([face(1)]))
    adj.submit(Wait())
    assert adj.monsters[0].facing == SOUTH  # swung at the player below it


def test_sleepers_keep_their_facing() -> None:
    g = make_game(ROOM, [(MINER, (2, 1), "asleep", (1, 0))], ScriptedRng([1]))
    g.submit(Wait())
    assert g.monsters[0].facing == (1, 0)


# -- flanking: +2 to hit from the rear arc ------------------------------------------------------


def test_attacking_a_monster_from_behind_adds_two_to_hit() -> None:
    # Fighter ATK +5 against DEF 0 needs 10: a 3 misses head-on and hits from behind
    front = stunned(make_game(ROOM, [(MINER, (2, 3), "hunting", NORTH)], ScriptedRng([face(3)])))
    assert attacked(front.submit(Move(0, 1)))[0].outcome is Outcome.MISS
    behind = stunned(
        make_game(ROOM, [(MINER, (2, 3), "hunting", SOUTH)], ScriptedRng([face(3), face(1)]))
    )
    assert attacked(behind.submit(Move(0, 1)))[0].outcome is Outcome.HIT


def test_the_rear_arc_includes_the_diagonals_behind() -> None:
    # the Miner at (2,3) faces south; (1,2) is north-west of it, inside the arc behind it
    rows = ["#######", "#.....#", "#.....#", "#.....#", "#<....#", "#######"]
    g = stunned(
        make_game(rows, [(MINER, (2, 3), "hunting", SOUTH)], ScriptedRng([face(3), face(1)]))
    )
    g.player.pos = Pos(1, 2)  # north-west of the Miner, which faces south: in its rear arc
    assert attacked(g.submit(Move(1, 1)))[0].outcome is Outcome.HIT


def test_monsters_behind_the_player_get_the_same_bonus() -> None:
    # Miner ATK +2 against the Fighter's DEF 1 needs 9; from behind it needs 7
    behind = make_game(ROOM, [(MINER, (2, 1), "hunting")], ScriptedRng([face(7), face(3)]))
    events = attacked(behind.submit(Wait()))  # the player faces south, the Miner is north
    assert events[0].outcome is Outcome.HIT and events[0].damage == 3 + 1 - 2
    front = make_game(ROOM, [(MINER, (2, 3), "hunting")], ScriptedRng([face(7)]))
    assert attacked(front.submit(Wait()))[0].outcome is Outcome.MISS


# -- Backstab ---------------------------------------------------------------------------------


def test_backstab_on_a_sleeper_hits_automatically_and_adds_two_d4() -> None:
    rng = ScriptedRng([face(1), face(4), face(3), face(2)])  # a natural 1 still hits; d6 4; 2d4 3+2
    g = make_game(ROOM, [(MINER, (2, 3), "asleep")], rng, class_id="rogue")
    events = g.submit(Move(0, 1))
    assert events[0] == Attacked(
        0, "Rook", 1, "Shambling Miner", 1, Outcome.HIT, 4 + 3 + 3 + 2, True
    )
    assert events[1] == Killed(1, "Shambling Miner") and rng.queue == []


def test_backstab_works_on_an_idle_monster_that_has_not_noticed_you() -> None:
    g = make_game(
        ROOM, [(MINER, (2, 3), "idle")], ScriptedRng([face(1), 0, 0, 0, 0]), class_id="rogue"
    )
    first = attacked(g.submit(Move(0, 1)))[0]
    assert first.outcome is Outcome.HIT and first.backstab


def test_backstab_on_a_stunned_target_hits_automatically() -> None:
    g = stunned(
        make_game(
            ROOM,
            [(MINER, (2, 3), "hunting", NORTH)],
            ScriptedRng([face(1), 0, 0, 0]),
            class_id="rogue",
        )
    )
    first = attacked(g.submit(Move(0, 1)))[0]
    assert first.outcome is Outcome.HIT and first.backstab


def test_a_head_on_fight_with_an_alert_monster_is_a_plain_attack() -> None:
    g = make_game(
        ROOM, [(MINER, (2, 3), "hunting", NORTH)], ScriptedRng([face(1), face(1)]), class_id="rogue"
    )
    first = attacked(g.submit(Move(0, 1)))[0]
    assert first.outcome is Outcome.MISS and not first.backstab


def test_flanking_alone_earns_the_bonus_dice_but_still_rolls_to_hit() -> None:
    # alert, facing away: +2 to hit and +2d4 damage; Rogue ATK +5 needs 10, so a 3 hits from behind
    rng = ScriptedRng(
        [face(3), face(1), face(1), face(1), face(1)]
    )  # hit, d6 1, 2d4 1+1, Miner swings (1)
    g = make_game(ROOM, [(MINER, (2, 3), "hunting", SOUTH)], rng, class_id="rogue")
    first = attacked(g.submit(Move(0, 1)))[0]
    assert (first.outcome, first.backstab, first.damage) == (Outcome.HIT, True, 1 + 3 + 1 + 1)


def test_a_fleeing_monster_can_be_backstabbed_but_must_still_be_hit() -> None:
    rng = ScriptedRng([face(1), face(1)])  # a natural 1 misses a fleeing monster; it then swings
    g = make_game(ROOM, [(MINER, (2, 3), "fleeing", NORTH)], rng, class_id="rogue")
    assert attacked(g.submit(Move(0, 1)))[0].outcome is Outcome.MISS
    rng = ScriptedRng([face(15), face(1), face(1), face(1), face(1)])
    g = make_game(ROOM, [(MINER, (2, 3), "fleeing", NORTH)], rng, class_id="rogue")
    hit = attacked(g.submit(Move(0, 1)))[0]
    assert hit.outcome is Outcome.HIT and hit.backstab


def test_several_conditions_still_add_the_dice_only_once() -> None:
    rng = ScriptedRng([face(5), face(2), face(1), face(1), face(1)])  # asleep AND flanked: one 2d4
    g = make_game(ROOM, [(MINER, (2, 3), "asleep", SOUTH)], rng, class_id="rogue")
    assert attacked(g.submit(Move(0, 1)))[0].damage == 2 + 3 + 1 + 1 and rng.queue == []


def test_a_critical_doubles_the_weapon_dice_but_not_the_backstab_dice() -> None:
    rng = ScriptedRng([face(20), face(2), face(3), face(1), face(1), face(1)])  # 2d6, 2d4, a swing
    g = make_game(ROOM, [(MINER, (2, 3), "asleep")], rng, class_id="rogue")
    hit = attacked(g.submit(Move(0, 1)))[0]
    assert hit.outcome is Outcome.CRIT and hit.damage == 2 + 3 + 3 + 1 + 1 and rng.queue == []


def test_fighters_and_rangers_get_no_backstab_and_no_automatic_hits() -> None:
    scripts = {
        "fighter": [face(1), 1, 1],
        "ranger": [face(1), face(1), 1, 1],
    }  # Rangers swing twice
    # (after the swings: the noise wake roll, then the sleeper's own)
    for class_id, script in scripts.items():
        g = make_game(ROOM, [(MINER, (2, 3), "asleep")], ScriptedRng(script), class_id=class_id)
        first = attacked(g.submit(Move(0, 1)))[0]
        assert first.outcome is Outcome.MISS and not first.backstab, class_id
