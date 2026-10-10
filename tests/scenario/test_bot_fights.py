"""Done criterion: every class can fight, win, and die against whatever a level holds.

The bot hunts everything but the Rogue Humans, fights back at whatever stands beside it, and never
retreats or heals, so these are sanity checks on the rules, not claims about difficulty."""

import pytest

from minetoofar.core.seed import Seed
from minetoofar.sim.bot import play
from minetoofar.sim.events import AbilityUsed, Command, Event, Killed, PlayerDied, StubbornInvoked
from minetoofar.sim.game import Game

SEEDS = [f"GOLD{n:04d}" for n in range(1, 21)]


def fight(
    seed: str, level: int, rank: int = 1, class_id: str = "fighter"
) -> tuple[Game, list[Event]]:
    game = Game.new(Seed.parse(seed), level, rank, class_id)
    events: list[Event] = []

    def submit(cmd: Command) -> list[Event]:
        got = game.submit(cmd)
        events.extend(got)
        return got

    play(game, submit, 2500)
    return game, events


def kills(events: list[Event]) -> int:
    return sum(isinstance(e, Killed) for e in events)


def check_sane(game: Game, events: list[Event]) -> None:
    hero = game.view().hero
    assert 0 <= game.player.hp <= game.player.max_hp
    assert 0 <= hero.armor_dur <= hero.armor_max
    assert game.dead == any(isinstance(e, PlayerDied) for e in events)
    assert (game.cause != "") == game.dead
    assert all(m.hp > 0 for m in game.monsters)
    assert len({m.pos for m in game.monsters}) == len(game.monsters)  # nobody shares a tile
    assert game.pos not in {m.pos for m in game.monsters}


@pytest.mark.parametrize("seed", SEEDS[:12])
def test_every_fight_ends_in_a_sane_state(seed: str) -> None:
    for level in (1, 4):
        game, events = fight(seed, level)
        check_sane(game, events)


def test_fighters_both_win_and_lose_on_level_one() -> None:
    results = [fight(seed, 1) for seed in SEEDS[:10]]
    deaths = sum(game.dead for game, _ in results)
    assert 0 < deaths < len(results), f"{deaths} deaths in {len(results)} fights"
    assert any(isinstance(e, StubbornInvoked) for _, events in results for e in events)


def test_a_higher_rank_kills_more_before_it_falls() -> None:
    low = sum(kills(fight(s, 5, rank=1)[1]) for s in SEEDS[:8])
    high = sum(kills(fight(s, 5, rank=5)[1]) for s in SEEDS[:8])
    assert high > low


def test_every_floor_has_something_to_fight() -> None:
    for level in range(1, 6):
        _, events = fight(SEEDS[0], level)
        assert kills(events) > 0, f"level {level}"


@pytest.mark.parametrize("class_id", ["fighter", "rogue", "ranger"])
def test_every_class_can_fight_a_floor_and_uses_its_ability(class_id: str) -> None:
    results = [fight(seed, 2, rank=3, class_id=class_id) for seed in SEEDS[:6]]
    for game, events in results:
        check_sane(game, events)
    assert any(isinstance(e, AbilityUsed) for _, events in results for e in events)
    assert sum(kills(events) for _, events in results) > 6
