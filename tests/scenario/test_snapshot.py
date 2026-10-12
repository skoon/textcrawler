"""A saved game restores exactly (GDD 11, M8 done criterion 1): save at some moment, load, play
500 more inputs on both, and the state never differs."""

import json
from typing import Any

import pytest

from minetoofar.core.rng import Rng
from minetoofar.core.seed import Seed
from minetoofar.sim.bot import choose, play
from minetoofar.sim.events import (
    Command,
    DropItem,
    Equip,
    Move,
    Pickup,
    Run,
    ToggleTorch,
    UseAbility,
    UseItem,
    Wait,
)
from minetoofar.sim.game import Game, GameOver
from minetoofar.sim.snapshot import (
    SnapshotError,
    carry_from_dict,
    carry_to_dict,
    game_from_dict,
    game_to_dict,
)

DIRS = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]


def through_json(d: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(d))


def restore(g: Game) -> Game:
    return game_from_dict(through_json(game_to_dict(g)))


def fresh(seed: str, level: int, rank: int = 1, class_id: str = "fighter") -> Game:
    return Game.new(Seed.parse(seed), level, rank, class_id)


def walk_it(g: Game, limit: int) -> None:
    play(g, g.submit, limit)


def only_plain_json(value: object, where: str = "state") -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            assert isinstance(k, str), f"{where}: key {k!r}"
            only_plain_json(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            only_plain_json(v, f"{where}[{i}]")
    else:
        assert value is None or type(value) in (bool, int, str), f"{where}: {value!r}"


# -- the state hash survives the trip ----------------------------------------------------------


@pytest.mark.parametrize("class_id", ["fighter", "rogue", "ranger"])
def test_a_fresh_level_round_trips(class_id: str) -> None:
    g = fresh("GOLD0007", 3, class_id=class_id)
    assert restore(g).state_hash() == g.state_hash()


@pytest.mark.parametrize(
    ("seed", "level", "rank", "class_id", "turns"),
    [
        ("GOLD0001", 2, 3, "fighter", 200),
        ("GOLD0011", 2, 3, "rogue", 150),
        ("GOLD0013", 2, 3, "ranger", 150),
        ("GOLD0016", 1, 5, "fighter", 250),
        ("GOLD0042", 5, 4, "fighter", 120),
    ],
)
def test_a_game_in_play_round_trips_at_the_end_of_the_walk(
    seed: str, level: int, rank: int, class_id: str, turns: int
) -> None:
    g = fresh(seed, level, rank, class_id)
    walk_it(g, turns)
    twin = restore(g)
    assert twin.state_hash() == g.state_hash()
    assert game_to_dict(twin) == game_to_dict(g)  # saving the loaded game saves the same thing


def test_the_state_is_plain_json_with_no_floats_or_odd_keys() -> None:
    g = fresh("GOLD0016", 1, 5)
    walk_it(g, 200)
    only_plain_json(game_to_dict(g))


def test_doors_opened_and_the_remembered_map_come_back() -> None:
    g = fresh("GOLD0001", 2, 3)
    walk_it(g, 120)
    twin = restore(g)
    assert twin.grid.to_bytes() == g.grid.to_bytes() != g.spec.tiles
    assert twin.view().vis == g.view().vis


def test_a_landed_crate_and_the_drops_still_to_come_come_back() -> None:
    g = fresh("GOLD0016", 1, 5)
    walk_it(g, 250)
    twin = restore(g)
    assert [(c.pos, c.number, c.lines, c.delivery_billed) for c in twin.crates] == [
        (c.pos, c.number, c.lines, c.delivery_billed) for c in g.crates
    ]
    assert [n for n, _ in twin._due] == [n for n, _ in g._due]


def test_a_dead_game_stays_dead() -> None:
    g = fresh("GOLD0004", 5, 1)
    walk_it(g, 2500)
    assert g.dead
    twin = restore(g)
    assert twin.dead and twin.cause == g.cause and twin.state_hash() == g.state_hash()
    with pytest.raises(GameOver):
        twin.submit(Wait())


def test_the_ledger_pack_and_purse_come_back() -> None:
    g = fresh("GOLD0016", 1, 5)
    walk_it(g, 250)
    g.account = g.account.__class__(wallet=7, debt=3, repair_plan=True, coupons=2)
    g.player.weapon_mods["company_pickaxe"] = (2, 1)
    g.player.plated.add("boiler_suit")
    g.player.hp_bonus = 3
    g.cleared, g.bounties, g.turns_before = 2, 1, 812  # levels already finished on this run
    twin = restore(g)
    assert twin.account == g.account and twin.ledger == g.ledger and twin.player == g.player
    assert (twin.cleared, twin.bounties, twin.turns_before) == (2, 1, 812)
    assert twin.state_hash() == g.state_hash()


def test_the_carry_between_levels_round_trips() -> None:
    g = fresh("GOLD0016", 1, 5)
    walk_it(g, 100)
    g.check_out()
    carry = g.carry_over()
    back = carry_from_dict(through_json(carry_to_dict(carry)))
    assert back == carry


# -- and play goes on the same ---------------------------------------------------------------------


def commands(game: Game, rolls: list[int], i: int) -> Command:
    """Mostly what the scripted player would do, sometimes something odd, all from fixed dice."""
    r = rolls[i]
    if r % 10 < 7:
        return choose(game) or Wait()
    pick = (r // 10) % 9
    dx, dy = DIRS[(r // 100) % 8]
    return [
        Move(dx, dy), Run(dx, dy), Wait(), ToggleTorch(), UseAbility(), Pickup(), UseItem(0),
        Equip(0), DropItem(0),
    ][pick]  # fmt: skip


def play_both(a: Game, b: Game, rolls: list[int], start: int, count: int) -> int:
    """Send the same inputs to both; returns how many were played before either died."""
    for i in range(start, start + count):
        if a.dead or b.dead:
            assert a.dead == b.dead
            return i - start
        command = commands(a, rolls, i)
        assert commands(b, rolls, i) == command  # the same position gives the same choice
        assert a.submit(command) == b.submit(command), f"events differ at input {i}"
        assert a.state_hash() == b.state_hash(), f"state differs after input {i}"
    return count


@pytest.mark.parametrize(
    ("seed", "level", "rank", "class_id"),
    [
        ("GOLD0001", 2, 3, "fighter"),
        ("GOLD0011", 2, 3, "rogue"),
        ("GOLD0013", 2, 3, "ranger"),
        ("GOLD0016", 1, 5, "fighter"),
        ("GOLD0042", 4, 5, "fighter"),
    ],
)
@pytest.mark.parametrize("cut", [0, 40, 150, 330])
def test_a_game_saved_at_any_moment_plays_on_exactly_like_the_original(
    seed: str, level: int, rank: int, class_id: str, cut: int
) -> None:
    dice = Rng(hash_free(seed, cut))
    rolls = [dice.below(100000) for _ in range(900)]
    a = fresh(seed, level, rank, class_id)
    for i in range(cut):
        if a.dead:
            break
        a.submit(commands(a, rolls, i))
    b = restore(a)
    assert b.state_hash() == a.state_hash()
    played = play_both(a, b, rolls, cut, 500)
    assert played > 0 or a.dead


@pytest.mark.parametrize(
    ("seed", "class_id"), [("GOLD0001", "fighter"), ("GOLD0011", "rogue"), ("GOLD0013", "ranger")]
)
def test_a_game_saved_in_the_middle_of_a_fight_plays_on_exactly_like_the_original(
    seed: str, class_id: str
) -> None:
    rolls = [Rng(hash_free(seed, 1)).below(100000) for _ in range(900)]
    a = fresh(seed, 2, 3, class_id)
    for _ in range(1500):
        if a.dead or a.adjacent_enemies():
            break
        a.submit(choose(a) or Wait())
    assert a.adjacent_enemies(), "no fight to save in the middle of"
    b = restore(a)
    assert b.state_hash() == a.state_hash()
    assert [m.id for m in b.adjacent_enemies()] == [m.id for m in a.adjacent_enemies()]
    assert play_both(a, b, rolls, 0, 300) > 0


def hash_free(seed: str, cut: int) -> int:
    """A dice seed made from the test's own inputs (no hash(), no clocks)."""
    return sum(ord(c) * (i + 1) for i, c in enumerate(seed)) * 1000 + cut


def test_at_least_one_scenario_runs_the_full_five_hundred_inputs() -> None:
    rolls = [Rng(7).below(100000) for _ in range(900)]
    a = fresh("GOLD0042", 4, 5)
    b = restore(a)
    assert play_both(a, b, rolls, 0, 500) >= 100


# -- bad data fails loudly -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "damage",
    [
        lambda d: d.pop("player"),
        lambda d: d.__setitem__("rng", "lots"),
        lambda d: d.__setitem__("seed", 12),
        lambda d: d["player"].__setitem__("hp", 1.5),
        lambda d: d["tiles_changed"].append([999, 999, 3]),
        lambda d: d["tiles_changed"].append([1, 1, 250]),
        lambda d: d.__setitem__("vis", "AAAA"),
        lambda d: d["monsters"].append({"id": 1}),
        lambda d: d["ledger"].pop("traps"),
    ],
)
def test_damaged_state_raises_a_snapshot_error_not_a_crash(damage: Any) -> None:
    d = through_json(game_to_dict(fresh("GOLD0007", 2)))
    damage(d)
    with pytest.raises(SnapshotError):
        game_from_dict(d)
