from dataclasses import replace

from minetoofar.content.balance import load_balance
from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.rng import Rng
from minetoofar.gen.drops import SupplyDrop
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.gen.spawns import Spawn, SpawnList
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.economy import Account
from minetoofar.sim.game import Game
from minetoofar.sim.traps import Trap

LEGEND = {
    " ": Tile.SOLID, "#": Tile.WALL, "%": Tile.ROCK, ".": Tile.FLOOR,
    ",": Tile.CAVE_FLOOR, "+": Tile.DOOR, "<": Tile.ENTRY, ">": Tile.EXIT, "/": Tile.DOOR_OPEN,
    "~": Tile.BRINE, ":": Tile.RUBBLE, "T": Tile.GRAVESTONE, "H": Tile.MONUMENT,
    "u": Tile.OPEN_GRAVE,
}  # fmt: skip


def grid_from_rows(rows: list[str]) -> Grid:
    grid = Grid(len(rows[0]), len(rows))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            grid.set(x, y, LEGEND[ch])
    return grid


def spec_from_rows(rows: list[str]) -> LevelSpec:
    """A hand-drawn LevelSpec: '<' marks the entry, '>' the exit (defaults to the entry)."""
    grid = grid_from_rows(rows)
    marks = {ch: Pos(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch in "<>"}
    entry = marks["<"]
    return LevelSpec(
        seed="TEST", level=1, width=grid.width, height=grid.height, tiles=grid.to_bytes(),
        rooms=(), entry=entry, exit=marks.get(">", entry), attempt=0,
    )  # fmt: skip


class ScriptedRng(Rng):
    """An Rng whose below() answers come from a list, so a test can force exact die faces."""

    def __init__(self, values: list[int]) -> None:
        super().__init__(0)
        self.queue = list(values)

    def below(self, n: int) -> int:
        value = self.queue.pop(0)  # an empty script raises IndexError: the code drew too much
        assert 0 <= value < n, f"scripted {value} is outside below({n})"
        return value


BALANCE = load_balance()
DATA = load_gamedata()
MINER = "shambling_miner"


def make_game(
    rows: list[str],
    monsters: list[tuple[str, tuple[int, int], str]]
    | list[tuple[str, tuple[int, int], str, tuple[int, int]]]
    | None = None,
    rng: Rng | None = None,
    rank: int = 1,
    level: int = 1,
    class_id: str = "fighter",
    traps: list[Trap] | None = None,
    graveyard: bool = False,
    pack: list[Item] | None = None,
    floor: list[FloorItem] | None = None,
    drops: dict[int, list[Item]] | None = None,
    account: Account | None = None,
    supply: list[SupplyDrop] | None = None,
) -> Game:
    """A Game on a hand-drawn map; monsters are (kind, (x, y), state) in spawn order."""
    spec = replace(spec_from_rows(rows), level=level)
    spawns = SpawnList(
        spec.seed,
        level,
        tuple(
            Spawn(m[0], Pos(*m[1]), m[2], m[3] if len(m) > 3 else (0, 1)) for m in monsters or []
        ),
    )
    game = Game(
        spec, spawns, BALANCE, DATA, rng or Rng(7), class_id, rank, traps or [], graveyard,
        floor=floor or [], drops=drops or {}, account=account or Account(),
        supply=supply or [],
    )  # fmt: skip
    if pack is not None:
        game.player.pack[:] = pack
    return game


def inert(game: Game) -> Game:
    """Freeze every monster: they stand where they are and never take a turn."""
    for m in game.monsters:
        m.ready_at = 10**9
    return game
