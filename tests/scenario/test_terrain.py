"""Brine, Rubble, graves, and props: what the new terrain does to the player (GDD 5.4, 7.1, 7.5)."""

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import (
    Attacked,
    Blocked,
    BlockReason,
    GraveFall,
    Move,
    PlayerDied,
    StubbornInvoked,
    ToggleTorch,
    TorchDropped,
    Wait,
)
from minetoofar.sim.statuses import apply_status, is_active
from tests.helpers import DATA, MINER, ScriptedRng, make_game

E = Move(1, 0)


def attacks(events: list[object]) -> list[Attacked]:
    return [e for e in events if isinstance(e, Attacked)]


def face(n: int) -> int:
    return n - 1


# -- Rubble ------------------------------------------------------------------------------------


def test_a_step_onto_rubble_takes_two_turns() -> None:
    g = make_game(["#####", "#<:.#", "#####"])
    g.submit(E)
    assert g.ticks == 200
    g.submit(E)
    assert g.ticks == 300  # the step off it costs the usual price


def test_overtime_scales_the_rubble_step_too() -> None:
    g = make_game(["#####", "#<:.#", "#####"])
    apply_status(g.player, "overtime", now=0, defs=DATA.statuses)
    g.submit(E)
    assert g.ticks == 120  # 200 * 60 // 100


def test_a_monster_crossing_rubble_pays_double_its_move_cost() -> None:
    g = make_game(["#########", "#<..:...#", "#########"], [(MINER, (5, 1), "hunting")])
    g.submit(Wait())  # the Miner steps onto the rubble at (4,1): 150 doubled
    assert g.monsters[0].pos == Pos(4, 1) and g.monsters[0].ready_at == 300


# -- Brine: Soaked and the torch -----------------------------------------------------------------


def test_standing_in_brine_soaks_you_and_the_effect_lingers_two_turns() -> None:
    g = make_game(["######", "#<~..#", "######"])
    g.submit(E)
    assert is_active(g.player, "soaked", g.ticks) and g.view().hero.defense == 0  # DEF 1 - 1
    g.submit(E)  # out of the water at 200: the soaking, which began at 100, lasts until 300
    assert is_active(g.player, "soaked", g.ticks) and g.view().hero.defense == 0
    g.submit(Wait())  # now 300: dry again
    assert not is_active(g.player, "soaked", g.ticks) and g.view().hero.defense == 1


def test_waiting_in_brine_keeps_refreshing_the_soaking() -> None:
    g = make_game(["######", "#<~..#", "######"])
    g.submit(E)
    for _ in range(5):
        g.submit(Wait())
    assert is_active(g.player, "soaked", g.ticks)


def test_soaked_lowers_defense_by_one_in_a_fight() -> None:
    # Miner ATK +2 against DEF 1 needs a 9; against a soaked DEF 0 it needs an 8
    wet = make_game(
        ["#####", "#~<.#", "#####"], [(MINER, (3, 1), "hunting")], ScriptedRng([face(8), face(3)])
    )
    apply_status(wet.player, "soaked", now=0, defs=DATA.statuses)
    assert attacks(wet.submit(Wait()))[0].outcome is Outcome.HIT
    dry = make_game(
        ["#####", "#~<.#", "#####"], [(MINER, (3, 1), "hunting")], ScriptedRng([face(8)])
    )
    assert attacks(dry.submit(Wait()))[0].outcome is Outcome.MISS


def test_walking_into_brine_with_a_lit_torch_may_lose_it() -> None:
    lose = make_game(["#####", "#<~.#", "#####"], rng=ScriptedRng([0]))
    lose.submit(ToggleTorch())
    events = lose.submit(E)
    assert TorchDropped() in events and not lose.torch_lit and lose.view().light_radius == 4
    keep = make_game(["#####", "#<~.#", "#####"], rng=ScriptedRng([1]))
    keep.submit(ToggleTorch())
    assert TorchDropped() not in keep.submit(E) and keep.torch_lit


def test_an_unlit_torch_is_safe_in_brine_and_costs_no_roll() -> None:
    g = make_game(["#####", "#<~.#", "#####"], rng=ScriptedRng([]))
    assert TorchDropped() not in g.submit(E)


def test_a_critical_hit_may_knock_a_lit_torch_loose() -> None:
    # Miner crit (natural 20): d6 doubled, then the one-in-four torch roll
    rng = ScriptedRng([face(20), face(1), face(1), 0])
    g = make_game(["#####", "#<..#", "#####"], [(MINER, (2, 1), "hunting")], rng)
    g.torch_lit, g.player.torch_left = True, 40000
    events = g.submit(Wait())
    assert TorchDropped() in events and not g.torch_lit
    assert rng.queue == []


def test_an_ordinary_hit_never_costs_the_torch() -> None:
    rng = ScriptedRng([face(15), face(1)])
    g = make_game(["#####", "#<..#", "#####"], [(MINER, (2, 1), "hunting")], rng)
    g.torch_lit, g.player.torch_left = True, 40000
    assert TorchDropped() not in g.submit(Wait()) and g.torch_lit


# -- Open graves -------------------------------------------------------------------------------


def test_falling_into_an_open_grave_hurts_and_costs_two_extra_turns() -> None:
    g = make_game(["#####", "#<u.#", "#####"], rng=ScriptedRng([face(3)]))
    events = g.submit(E)
    assert GraveFall(Pos(2, 1), 3) in events
    assert g.player.hp == 27 and g.ticks == 100 + 200


def test_a_grave_fall_ignores_armor_and_can_be_survived_with_stubborn() -> None:
    g = make_game(["#####", "#<u.#", "#####"], rng=ScriptedRng([face(4)]))
    g.player.hp = 2
    events = g.submit(E)
    assert StubbornInvoked() in events and g.player.hp == 1 and g.player.body_dur == 18


def test_a_grave_can_kill() -> None:
    g = make_game(["#####", "#<u.#", "#####"], rng=ScriptedRng([face(4)]))
    g.player.hp, g.player.stubborn_used = 2, True
    events = g.submit(E)
    assert PlayerDied("an open grave") in events


# -- props -------------------------------------------------------------------------------------


def test_gravestones_and_monuments_block_movement() -> None:
    g = make_game(["######", "#<TH.#", "######"])
    assert g.submit(E) == [Blocked(Pos(2, 1), BlockReason.WALL)]
    assert g.ticks == 0 and g.grid.get(2, 1) == Tile.GRAVESTONE


def test_only_monuments_hide_what_is_behind_them() -> None:
    rows = ["#######", "#<.T.:#", "#######"]
    seen = make_game(rows).view()
    assert seen.vis[1 * 7 + 5] == 2  # visible past the gravestone
    rows = ["#######", "#<.H.:#", "#######"]
    hidden = make_game(rows).view()
    assert hidden.vis[1 * 7 + 4] == 0  # nothing beyond the monument
