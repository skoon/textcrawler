"""What lies on the floor and what dies with a monster (generation stage `loot`, GDD 8.3, 8.4,
9.6, 10.4 step 10). Documents get their own stream (`level/N/docs`) for the choice of words."""

import hashlib
from dataclasses import dataclass

from minetoofar.content.balance import LEVELS
from minetoofar.content.docs import load_docs
from minetoofar.content.gamedata import GameData, found_charge, load_gamedata
from minetoofar.content.loot import ANY_FIND, DropDef, LootTables, load_loot
from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Grid
from minetoofar.core.rng import Rng
from minetoofar.core.seed import Seed
from minetoofar.gen.features import Features
from minetoofar.gen.humans import Humans
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.gen.rooms import floor_tiles, room_containing
from minetoofar.gen.spawns import SpawnList
from minetoofar.gen.traps import Traps


class LootError(RuntimeError):
    pass


@dataclass(frozen=True)
class LootItem:
    """One find. A document is `memo`, `coupon` or `map`, and `text` picks its words."""

    id: str
    qty: int = 1
    charge: int = 0  # gold billed per use (consumables)
    dur: int = 0  # condition (armor)
    text: int = 0

    def line(self) -> str:
        return f"{self.id} {self.qty} {self.charge} {self.dur} {self.text}"


@dataclass(frozen=True)
class Loot:
    seed: str
    level: int
    items: tuple[tuple[Pos, LootItem], ...]  # sorted (y, x)
    drops: tuple[tuple[int, LootItem], ...]  # (monster number, what it leaves), sorted

    def dump(self) -> str:
        lines = ["AMTF-LOOT", f"seed {self.seed}", f"level {self.level}"]
        lines.append(f"items {len(self.items)}")
        lines += [f"item {p.x} {p.y} {i.line()}" for p, i in self.items]
        lines.append(f"drops {len(self.drops)}")
        lines += [f"drop {mid} {i.line()}" for mid, i in self.drops]
        return "\n".join(lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dump().encode("ascii")).hexdigest()


_SOURCES = {"weapon": "weapons", "armor": "armor", "shield": "shields", "hat": "hats",
            "trinket": "trinkets"}  # fmt: skip


class Roller:
    """The dice for one level's finds."""

    def __init__(self, rng: Rng, docs: Rng, tables: LootTables, data: GameData, level: int) -> None:
        self.rng, self.docs, self.t, self.data, self.level = rng, docs, tables, data, level
        self.book = load_docs()

    def consumable(self) -> LootItem:
        item = self.rng.weighted(self.t.consumables)
        return LootItem(item, 1, found_charge(self.data.items.consumables[item]))

    def valuable(self, count: int = 1) -> LootItem:
        pairs = [(k, v.weight) for k, v in self.data.items.valuables.items()]
        return LootItem(self.rng.weighted(pairs), count)

    def document(self) -> LootItem:
        kind = self.docs.weighted(self.t.documents)
        return LootItem(kind, text=self.docs.below(len(self.book.texts[kind])))

    def equipment(self) -> LootItem:
        sub = self.rng.weighted(self.t.equipment)
        table = getattr(self.data.items, _SOURCES[sub])
        i = self.level - 1
        roll, first, second = self.rng.below(100), self.t.tiers[0][i], self.t.tiers[1][i]
        tier = 1 if roll < first else 2 if roll < first + second else 3
        while tier > 1 and not any(d.tier == tier for d in table.values()):
            tier -= 1  # nothing of that tier in this kind of gear: the best below it
        candidates = [k for k, d in table.items() if d.tier == tier]
        if not candidates:
            raise LootError(f"no tier-{tier} {sub} to find")
        item = self.rng.pick(candidates)
        if sub != "armor":
            return LootItem(item)
        top = table[item].dur
        pct = self.t.condition_min_pct + self.rng.below(100 - self.t.condition_min_pct + 1)
        return LootItem(item, dur=max(1, top * pct // 100))

    def find(self, categories: tuple[tuple[str, int], ...]) -> LootItem:
        kind = self.rng.weighted(categories)
        if kind == "consumable":
            return self.consumable()
        if kind == "valuable":
            return self.valuable()
        if kind == "equipment":
            return self.equipment()
        return self.document()

    def drop(self, d: DropDef) -> LootItem:
        if d.item == ANY_FIND:
            pairs = [(k, w) for k, w in self.t.categories if k in ("valuable", "document")]
            return self.find(tuple(pairs))
        return self.valuable_of(d.item, 1 + self.rng.below(d.max))

    def valuable_of(self, item: str, count: int) -> LootItem:
        return LootItem(item, count)


def generate_loot(
    seed: Seed,
    level: int,
    spec: LevelSpec,
    features: Features,
    humans: Humans,
    traps: Traps,
    monsters: SpawnList,
    data: GameData | None = None,
) -> Loot:
    """`spec` is the level with its features laid in; `monsters` has the human first."""
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1-{LEVELS}, got {level}")
    game_data, tables = data or load_gamedata(), load_loot()
    roller = Roller(
        seed.rng().derive("level", level, "loot"),
        seed.rng().derive("level", level, "docs"),
        tables, game_data, level,
    )  # fmt: skip
    rng = roller.rng
    grid = Grid(spec.width, spec.height, spec.tiles)
    kinds = list(features.room_kinds)
    kinds[humans.room_id] = "lair"
    weight_of = dict(tables.rooms)
    taken = {spec.entry, spec.exit, humans.pos}
    taken |= {m.pos for m in monsters.spawns} | {p for p, _ in traps.traps}
    entry, exit_ = room_containing(spec.rooms, spec.entry), room_containing(spec.rooms, spec.exit)
    free = {
        r.id: [p for p in floor_tiles(grid, r) if p not in taken]
        for r in spec.rooms
        if r is not entry and r is not exit_
    }

    def place(item: LootItem, room: int | None = None) -> tuple[Pos, LootItem]:
        if room is None:
            options = [(rid, weight_of.get(kinds[rid], 0)) for rid, tiles in free.items() if tiles]
            options = [o for o in options if o[1] > 0]
            if not options:
                raise LootError("no room has space for the loot")
            room = rng.weighted(options)
        if not free[room]:
            raise LootError(f"room {room} has no free tile")
        pos = rng.pick(free[room])
        free[room].remove(pos)
        return pos, item

    vaults = kinds.count("mausoleum")
    count = tables.base_items + tables.per_level_items * level + tables.extra_per_vault * vaults
    categories = tables.categories
    # The lair's own documents go down first, so a crowded room cannot crowd them out.
    placed = [place(roller.document(), humans.room_id) for _ in range(tables.lair_documents)]
    capped = tuple((k, w) for k, w in categories if k != "document")
    documents = 0
    for _ in range(count):
        item = roller.find(capped if documents >= tables.document_cap else categories)
        documents += item.id in ("memo", "coupon", "map")
        placed.append(place(item))
    drops = []
    for number, spawn in enumerate(monsters.spawns, 1):
        if spawn.kind in tables.drops:
            drops.append((number, roller.drop(tables.drops[spawn.kind])))
    placed.sort(key=lambda pi: (pi[0].y, pi[0].x))
    return Loot(spec.seed, level, tuple(placed), tuple(drops))


__all__ = ["Loot", "LootError", "LootItem", "generate_loot", "room_containing"]
