"""Walk generated levels, empty of monsters, from the entry stairs to the Down Shaft."""

from time import perf_counter

import pytest

from minetoofar.core.geometry import DIRS8
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.pathing import distance_map
from minetoofar.core.seed import Seed
from minetoofar.gen.layout import generate_level
from minetoofar.gen.spawns import SpawnList
from minetoofar.sim.events import DoorOpened, Event, Move, Moved, ToggleTorch
from minetoofar.sim.game import REMEMBERED, VISIBLE, Game
from tests.helpers import BALANCE, DATA

SEEDS = [f"GOLD{n:04d}" for n in range(1, 101)]
FOV_BUDGET_MS = 5


def empty_level(seed: str, level: int) -> Game:
    """The real level with no monsters, so walking is about doors, fog, and the camera alone."""
    parsed = Seed.parse(seed)
    spec = generate_level(parsed, level)
    rng = parsed.rng().derive("play", level)
    return Game(spec, SpawnList(spec.seed, level, ()), BALANCE, DATA, rng)


def route(game: Game) -> list[tuple[int, int]]:
    """Steepest-descent steps from the entry to the exit over a fresh distance map."""
    spec = game.spec
    grid = Grid(spec.width, spec.height, spec.tiles)
    dist = distance_map(grid, spec.exit)
    steps: list[tuple[int, int]] = []
    here = spec.entry
    while here != spec.exit:
        for d in DIRS8:
            nxt = here.step(d)
            cost = 10 if d[0] == 0 or d[1] == 0 else 14
            if grid.can_step(here, d) and dist.get(nxt, 1 << 60) + cost == dist[here]:
                steps.append(d)
                here = nxt
                break
        else:
            raise AssertionError(f"no way forward from {here}")
    return steps


def walk(game: Game) -> tuple[list[Event], list[float]]:
    events: list[Event] = []
    times: list[float] = []
    for d in route(game):
        while True:
            start = perf_counter()
            step = game.submit(Move(*d))
            times.append(perf_counter() - start)
            events += step
            if not isinstance(step[-1], DoorOpened):
                break  # a bumped door opens in place; repeat the same step to walk through
    return events, times


@pytest.mark.parametrize("seed", SEEDS)
def test_level_one_can_be_walked_from_entry_to_exit(seed: str) -> None:
    game = empty_level(seed, 1)
    events, _ = walk(game)
    spec = game.spec
    assert game.pos == spec.exit
    moved = [e for e in events if isinstance(e, Moved)]
    doors = [e for e in events if isinstance(e, DoorOpened)]
    assert all(isinstance(e, Moved | DoorOpened) for e in events)  # nothing was refused
    assert game.ticks == 100 * (len(moved) + len(doors))
    view = game.view()
    for e in moved:
        assert view.vis[e.pos.y * view.width + e.pos.x] in (REMEMBERED, VISIBLE)
    assert Tile(view.tiles[spec.exit.y * view.width + spec.exit.x]) == Tile.EXIT
    assert view.vis[spec.exit.y * view.width + spec.exit.x] == VISIBLE


def test_every_door_on_the_way_gets_opened_exactly_once() -> None:
    game = empty_level("GOLD0003", 4)
    events, _ = walk(game)
    opened = [e.pos for e in events if isinstance(e, DoorOpened)]
    assert len(opened) == len(set(opened))
    assert all(
        Tile(game.view().tiles[p.y * game.spec.width + p.x]) == Tile.DOOR_OPEN for p in opened
    )


@pytest.mark.parametrize(("seed", "level"), [("BRASSLAMP42", 3), ("GOLD0007", 5), ("GOLD0042", 2)])
def test_each_turn_costs_well_under_a_frame(seed: str, level: int) -> None:
    game = empty_level(seed, level)
    game.submit(ToggleTorch())  # the widest light is the worst case
    _, times = walk(game)
    mean_ms = 1000 * sum(times) / len(times)
    assert mean_ms < FOV_BUDGET_MS, f"{mean_ms:.2f} ms per turn"
