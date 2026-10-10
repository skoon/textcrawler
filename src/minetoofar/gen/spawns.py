"""Monster placement (generation stage `spawns`, GDD 9.4, 9.5, 10.4 step 9).

Its own streams, `level/N/spawns` and `level/N/spawn_facing`, and its own dump and hash, so layout
goldens never move when this stage changes.
"""

import hashlib
from dataclasses import dataclass

from minetoofar.content.balance import LEVELS, SpawnParams, load_balance
from minetoofar.content.gamedata import GameData, MonsterDef
from minetoofar.core.geometry import DIRS8, Pos, octile
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.pathing import distance_map
from minetoofar.core.seed import Seed
from minetoofar.gen.features import Features
from minetoofar.gen.humans import Humans
from minetoofar.gen.level_spec import LevelSpec, Spawn
from minetoofar.gen.rooms import floor_tiles, room_containing
from minetoofar.gen.theme import Theme

RESERVED_BEASTS = ("cave_vermin", "gem_badger")  # the guaranteed beast is one of these


class SpawnError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpawnList:
    seed: str
    level: int
    spawns: tuple[Spawn, ...]

    def dump(self) -> str:
        lines = [
            "AMTF-SPAWNS",
            f"seed {self.seed}",
            f"level {self.level}",
            f"count {len(self.spawns)}",
        ]
        lines += [
            f"spawn {i} {s.kind} {s.pos.x} {s.pos.y} {s.state} {s.facing[0]} {s.facing[1]} {s.pack}"
            for i, s in enumerate(self.spawns)
        ]
        return "\n".join(lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dump().encode("ascii")).hexdigest()


def threat_spent(spawns: SpawnList, data: GameData) -> int:
    """Budget used: each monster's threat, but a whole Vermin pack costs one pack's worth."""
    alone = sum(data.monsters[s.kind].threat for s in spawns.spawns if s.pack == 0)
    packs = {s.pack: s.kind for s in spawns.spawns if s.pack}
    return alone + sum(data.monsters[kind].threat for kind in packs.values())


class _Board:
    """Which tiles and rooms are still open for a monster."""

    def __init__(
        self, spec: LevelSpec, features: Features, humans: Humans, params: SpawnParams
    ) -> None:
        grid = Grid(spec.width, spec.height, spec.tiles)
        dist = distance_map(grid, spec.entry)
        banned = {
            room_containing(spec.rooms, spec.entry).id,  # type: ignore[union-attr]
            room_containing(spec.rooms, spec.exit).id,  # type: ignore[union-attr]
        }
        self.params = params
        self.features = features
        self.used: set[Pos] = {humans.pos}
        self.count = {humans.room_id: 1}
        self.floor: dict[int, list[Pos]] = {}
        self.brine: dict[int, list[Pos]] = {}
        self.graves: dict[int, list[Pos]] = {}
        for room in spec.rooms:
            if room.id in banned:
                continue

            def far(p: Pos) -> bool:
                return dist.get(p, -1) >= params.min_entry_distance

            self.floor[room.id] = [p for p in floor_tiles(grid, room) if far(p)]
            for found, tile in ((self.brine, Tile.BRINE), (self.graves, Tile.OPEN_GRAVE)):
                found[room.id] = [
                    Pos(x, y)
                    for y in range(room.y, room.y + room.h)
                    for x in range(room.x, room.x + room.w)
                    if grid.get(x, y) == tile and far(Pos(x, y))
                ]

    def open_rooms(self, tiles: dict[int, list[Pos]], needed: int = 1) -> list[int]:
        """Rooms with room for `needed` more actors and as many free tiles of the wanted kind."""
        return [
            rid
            for rid, spots in tiles.items()
            if self.count.get(rid, 0) + needed <= self.params.room_cap
            and sum(p not in self.used for p in spots) >= needed
        ]

    def free(self, tiles: dict[int, list[Pos]], rid: int) -> list[Pos]:
        return [p for p in tiles[rid] if p not in self.used]

    def take(self, rid: int, pos: Pos) -> None:
        self.used.add(pos)
        self.count[rid] = self.count.get(rid, 0) + 1


def generate_spawns(
    seed: Seed,
    level: int,
    spec: LevelSpec,
    features: Features,
    theme: Theme,
    humans: Humans,
    data: GameData,
) -> SpawnList:
    """`spec` is the level with its features laid in; the human is already placed."""
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1-{LEVELS}, got {level}")
    params = load_balance().spawns
    rng = seed.rng().derive("level", level, "spawns")
    facing_rng = seed.rng().derive("level", level, "spawn_facing")
    board = _Board(spec, features, humans, params)
    budget = params.budget_base + params.budget_per_level * level
    if theme.graveyard:
        budget = budget * params.graveyard_budget_pct // 100
    spawns: list[Spawn] = []
    packs = 0

    def weight(m: MonsterDef) -> int:
        return m.grave_weight if theme.graveyard else m.weight

    def pack_size(m: MonsterDef) -> int:
        return params.pack_min if m.behavior == "swarm" else 1

    def placeable(m: MonsterDef) -> bool:
        if m.behavior == "eel":
            return bool(board.open_rooms(board.brine))
        return bool(board.open_rooms(board.floor, pack_size(m)))

    def place(kind: str) -> None:
        nonlocal packs
        m = data.monsters[kind]

        def facing() -> tuple[int, int]:
            return facing_rng.pick(DIRS8)

        if m.behavior == "eel":
            rid = rng.pick(board.open_rooms(board.brine))
            pos = rng.pick(board.free(board.brine, rid))
            board.take(rid, pos)
            spawns.append(Spawn(kind, pos, "submerged", facing()))
            return
        graves = board.open_rooms(board.graves)
        if kind == "shambling_miner" and graves and rng.chance(params.grave_buried_pct, 100):
            rid = rng.pick(graves)
            pos = rng.pick(board.free(board.graves, rid))
            board.take(rid, pos)
            spawns.append(Spawn(kind, pos, "buried", facing()))
            return
        rid = rng.pick(board.open_rooms(board.floor, pack_size(m)))
        pct = params.bunk_asleep_pct if features.room_kinds[rid] == "bunk" else params.asleep_pct
        state = "asleep" if rng.chance(pct, 100) else "idle"
        pos = rng.pick(board.free(board.floor, rid))
        members = [pos]
        if m.behavior == "swarm":
            packs += 1
            size = rng.randrange(params.pack_min, params.pack_max + 1)
            room_left = params.room_cap - board.count.get(rid, 0)
            near = sorted(
                (p for p in board.free(board.floor, rid) if p != pos),
                key=lambda p: (octile(p, pos), p.y, p.x),
            )
            members += near[: max(0, min(size, room_left) - 1)]
        for p in members:
            board.take(rid, p)
            spawns.append(
                Spawn(kind, p, state, facing(), pack=packs if m.behavior == "swarm" else 0)
            )

    # One beast is guaranteed before anything else is drawn (GDD 9.5 step 2).
    reserved = [
        (k, weight(data.monsters[k])) for k in RESERVED_BEASTS if placeable(data.monsters[k])
    ]
    if not reserved:
        raise SpawnError("no room for the guaranteed beast")
    kind = rng.weighted(reserved)
    place(kind)
    budget -= data.monsters[kind].threat

    while True:
        options = [
            (k, weight(m))
            for k, m in data.monsters.items()
            if weight(m) > 0 and m.min_level <= level and m.threat <= budget and placeable(m)
        ]
        if not options:
            break
        kind = rng.weighted(options)
        place(kind)
        budget -= data.monsters[kind].threat
    return SpawnList(spec.seed, level, tuple(spawns))
