"""Hidden static traps (GDD 9.7, 10.4 step 8): in corridors and doorways, plus the pre-laid pair
in Prospector Vane's camp. Vane lays more at runtime; that is the game's business, not this
stage's.

Only a Rogue can disarm a trap, so a trap may never be the only way on: every walkable tile that
is not itself a trap must stay reachable from the entry with all the traps counted as walls."""

import hashlib
from dataclasses import dataclass

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.geometry import DIRS8, Pos
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.rng import Rng
from minetoofar.core.seed import Seed
from minetoofar.gen.features import Features
from minetoofar.gen.humans import Humans
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.gen.rooms import floor_tiles, room_containing

_PLAIN = (Tile.FLOOR, Tile.CAVE_FLOOR)
_ORTHOGONAL = ((0, 1), (0, -1), (1, 0), (-1, 0))


@dataclass(frozen=True)
class Traps:
    seed: str
    level: int
    traps: tuple[tuple[Pos, str], ...]  # (position, data key), sorted (y, x)

    def dump(self) -> str:
        lines = [
            "AMTF-TRAPS",
            f"seed {self.seed}",
            f"level {self.level}",
            f"count {len(self.traps)}",
        ]
        lines += [f"trap {p.x} {p.y} {kind}" for p, kind in self.traps]
        return "\n".join(lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dump().encode("ascii")).hexdigest()


def _spots(grid: Grid, spec: LevelSpec, features: Features) -> list[Pos]:
    """Corridor tiles, and the floor tile on either side of a door, outside the entry room."""
    entry = room_containing(spec.rooms, spec.entry)
    found = []
    for y in range(spec.height):
        for x in range(spec.width):
            p = Pos(x, y)
            if grid.get(x, y) not in _PLAIN or (entry and room_containing([entry], p)):
                continue
            corridor = room_containing(spec.rooms, p) is None
            doorway = any(
                grid.in_bounds(x + dx, y + dy) and grid.get(x + dx, y + dy) == Tile.DOOR
                for dx, dy in _ORTHOGONAL
            )
            if corridor or doorway:
                found.append(p)
    return found


def scatter_safely(
    rng: Rng, grid: Grid, entry: Pos, spots: list[Pos], count: int, taken: set[Pos]
) -> list[Pos]:
    """Up to `count` of `spots` at random, no two touching, none where it would shut off part of
    the level from `entry` once every trap in `taken` is counted as a wall. Fewer if the level has
    no more safe spots; the traps chosen are added to `taken`."""
    pool = list(spots)
    rng.shuffle(pool)
    everything = grid.count_reachable(entry)
    chosen: list[Pos] = []
    for p in pool:
        if len(chosen) == count:
            break
        if p in taken or any(p.step(d) in taken for d in DIRS8):
            continue
        if grid.count_reachable(entry, [*taken, p]) != everything - len(taken) - 1:
            continue
        chosen.append(p)
        taken.add(p)
    return sorted(chosen, key=lambda q: (q.y, q.x))


def generate_traps(
    seed: Seed, level: int, spec: LevelSpec, features: Features, humans: Humans
) -> Traps:
    """`spec` is the level with its features laid in."""
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1-{LEVELS}, got {level}")
    bal = load_balance()
    kinds = list(load_gamedata().traps)
    rng = seed.rng().derive("level", level, "traps")
    grid = Grid(spec.width, spec.height, spec.tiles)
    taken: set[Pos] = set()
    spots = _spots(grid, spec, features)
    placed = scatter_safely(rng, grid, spec.entry, spots, bal.trap_counts[level - 1], taken)
    if humans.room_kind == "prospector_camp":
        room = spec.rooms[humans.room_id]
        inside = [p for p in floor_tiles(grid, room) if p != humans.pos]
        placed += scatter_safely(rng, grid, spec.entry, inside, bal.humans.camp_traps, taken)
    chosen = sorted(placed, key=lambda p: (p.y, p.x))
    return Traps(spec.seed, level, tuple((p, rng.pick(kinds)) for p in chosen))
