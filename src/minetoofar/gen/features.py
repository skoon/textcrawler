"""Room types and what fills them (GDD 9.3, 10.4 step 4): Brine in Flooded Galleries, Rubble in
Collapses, and on a graveyard floor the Cemetery Plots and the Mausoleum.

Its output is a list of room kinds and a list of tile replacements; the layout itself is not
touched, so the layout hash never moves when this stage changes.
"""

import hashlib
from dataclasses import dataclass, replace

from minetoofar.content.balance import LEVELS, FeatureParams, load_balance
from minetoofar.core.geometry import DIRS8, Pos
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.rng import Rng
from minetoofar.core.seed import Seed
from minetoofar.gen.level_spec import TILE_CHARS, LevelSpec, Room
from minetoofar.gen.rooms import flood_candidates, floor_tiles, interior_tiles, room_containing
from minetoofar.gen.theme import Theme


class FeatureError(RuntimeError):
    pass


@dataclass(frozen=True)
class Features:
    seed: str
    level: int
    room_kinds: tuple[str, ...]  # entry exit gallery flooded bunk collapse cemetery mausoleum
    tiles: tuple[tuple[Pos, Tile], ...]  # replacements for plain floor, sorted (y, x)

    def dump(self) -> str:
        lines = ["AMTF-FEATURES", f"seed {self.seed}", f"level {self.level}"]
        lines.append(f"rooms {len(self.room_kinds)}")
        lines += [f"room {i} {kind}" for i, kind in enumerate(self.room_kinds)]
        lines.append(f"tiles {len(self.tiles)}")
        lines += [f"tile {p.x} {p.y} {TILE_CHARS[t]}" for p, t in self.tiles]
        return "\n".join(lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dump().encode("ascii")).hexdigest()


def apply_features(spec: LevelSpec, features: Features) -> LevelSpec:
    """The layout with its features laid in: the map the game is played on."""
    tiles = bytearray(spec.tiles)
    for p, t in features.tiles:
        tiles[p.y * spec.width + p.x] = t
    return replace(spec, tiles=bytes(tiles))


def _scatter(rng: Rng, spots: list[Pos], count: int, taken: set[Pos]) -> list[Pos]:
    """Up to `count` of `spots`, chosen at random, no two (nor any in `taken`) touching, so a
    walkable ring around every prop is always left and the room can never be cut in two."""
    pool = list(spots)
    rng.shuffle(pool)
    crowded = set(spots)
    # Tiles with the fewest neighbours first (corners before the middle), so the props pack in
    # and a second kind still has somewhere to go; the shuffle breaks the ties.
    pool.sort(key=lambda q: sum(q.step(d) in crowded for d in DIRS8))
    chosen: list[Pos] = []
    for p in pool:
        if len(chosen) == count:
            break
        if p in taken or any(p.step(d) in taken for d in DIRS8):
            continue
        chosen.append(p)
        taken.add(p)
    return sorted(chosen, key=lambda q: (q.y, q.x))


def _mausoleum(rng: Rng, grid: Grid, rooms: list[Room], count: int) -> tuple[Room, list[Pos]]:
    """A room with space for all the tombs, else the roomiest one (a cramped cave)."""
    order = list(rooms)
    rng.shuffle(order)
    best: tuple[Room, list[Pos]] | None = None
    for room in order:
        tombs = _scatter(rng, interior_tiles(grid, room), count, set())
        if len(tombs) == count:
            return room, tombs
        if best is None or len(tombs) > len(best[1]):
            best = (room, tombs)
    assert best is not None
    return best


def _cemetery(rng: Rng, grid: Grid, room: Room, p: FeatureParams, out: dict[Pos, Tile]) -> None:
    inner = interior_tiles(grid, room)
    if not inner:
        return
    taken: set[Pos] = set()
    graves = _scatter(rng, inner, max(1, len(inner) * p.grave_pct // 100), taken)
    stones = _scatter(rng, inner, max(1, len(inner) * p.gravestone_pct // 100), taken)
    out.update({q: Tile.GRAVESTONE for q in stones})
    out.update({q: Tile.OPEN_GRAVE for q in graves})


def generate_features(seed: Seed, level: int, spec: LevelSpec, theme: Theme) -> Features:
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1-{LEVELS}, got {level}")
    p = load_balance().features
    rng = seed.rng().derive("level", level, "features")
    grid = Grid(spec.width, spec.height, spec.tiles)
    entry, exit_ = room_containing(spec.rooms, spec.entry), room_containing(spec.rooms, spec.exit)
    assert entry is not None and exit_ is not None
    kinds = ["gallery"] * len(spec.rooms)
    kinds[entry.id], kinds[exit_.id] = "entry", "exit"
    out: dict[Pos, Tile] = {}

    guaranteed = p.level3_flooded_min if level == 3 else 1  # the layout stage ensures these exist
    wanted = rng.randrange(p.level3_flooded_min, p.level3_flooded_max + 1) if level == 3 else 1
    eligible = flood_candidates(grid, list(spec.rooms), {entry.id, exit_.id}, p.flood_min_pct)
    if len(eligible) < guaranteed:
        raise FeatureError(f"only {len(eligible)} rooms can be flooded, {guaranteed} needed")
    rng.shuffle(eligible)
    for room in eligible[:wanted]:  # a roll above what the level can flood just floods them all
        kinds[room.id] = "flooded"
        out.update({q: Tile.BRINE for q in interior_tiles(grid, room)})

    open_rooms = [r for r in spec.rooms if kinds[r.id] == "gallery"]
    if theme.graveyard:
        tomb_room, tombs = _mausoleum(rng, grid, open_rooms, p.monuments)
        kinds[tomb_room.id] = "mausoleum"
        out.update({q: Tile.MONUMENT for q in tombs})
        for room in open_rooms:
            if room is not tomb_room and rng.chance(p.cemetery_pct, 100):
                kinds[room.id] = "cemetery"
                _cemetery(rng, grid, room, p, out)
    for room in open_rooms:
        if kinds[room.id] != "gallery":
            continue
        if room.cave and rng.chance(p.collapse_pct, 100):
            kinds[room.id] = "collapse"
            out.update(
                {q: Tile.RUBBLE for q in floor_tiles(grid, room) if rng.chance(p.rubble_pct, 100)}
            )
        elif rng.chance(p.bunk_pct, 100):
            kinds[room.id] = "bunk"
    tiles = tuple(sorted(out.items(), key=lambda item: (item[0].y, item[0].x)))
    return Features(spec.seed, level, tuple(kinds), tiles)
