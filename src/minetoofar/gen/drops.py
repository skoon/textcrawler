"""Supply drops (generation stage `drops`, GDD 8.5, 10.4 step 11): how many crates a level gets,
the turn each lands, and what is in it. All rolled now, so a seed always shows the same crates."""

import hashlib
from dataclasses import dataclass

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.gamedata import GameData, load_gamedata
from minetoofar.content.loot import load_loot
from minetoofar.core.seed import Seed
from minetoofar.gen.loot import Roller


@dataclass(frozen=True)
class SupplyLine:
    item: str
    qty: int
    dur: int  # condition (armor): crates deliver it new


@dataclass(frozen=True)
class SupplyDrop:
    trigger: int  # the turn on the level that it lands
    lines: tuple[SupplyLine, ...]  # the equipment line, if any, is last


@dataclass(frozen=True)
class Drops:
    seed: str
    level: int
    drops: tuple[SupplyDrop, ...]

    def dump(self) -> str:
        lines = [
            "AMTF-DROPS",
            f"seed {self.seed}",
            f"level {self.level}",
            f"count {len(self.drops)}",
        ]
        for i, d in enumerate(self.drops, 1):
            lines.append(f"drop {i} turn {d.trigger}")
            lines += [f"line {ln.item} {ln.qty} {ln.dur}" for ln in d.lines]
        return "\n".join(lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dump().encode("ascii")).hexdigest()


def generate_drops(seed: Seed, level: int, data: GameData | None = None) -> Drops:
    """A pure function of (seed, level), on its own stream `level/N/drops`."""
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1-{LEVELS}, got {level}")
    game_data, tables, p = data or load_gamedata(), load_loot(), load_balance().supply
    rng = seed.rng().derive("level", level, "drops")
    roller = Roller(
        rng, seed.rng().derive("level", level, "drops", "docs"), tables, game_data, level
    )
    count = rng.weighted([(0, p.none_weight), (1, p.one_weight), (2, p.two_weight)])
    triggers: list[int] = []
    if count == 1:
        triggers = [rng.randrange(p.trigger_min, p.trigger_max + 1)]
    elif count == 2:
        first = rng.randrange(p.trigger_min, p.trigger_max - p.second_gap + 1)
        triggers = [first, rng.randrange(first + p.second_gap, p.trigger_max + 1)]
    drops = []
    for turn in triggers:
        stock = list(tables.consumables)
        lines = []
        for _ in range(p.lines):
            item = rng.weighted(stock)
            stock = [(k, w) for k, w in stock if k != item]
            lines.append(SupplyLine(item, rng.randrange(1, p.qty_max + 1), 0))
        if rng.chance(p.equipment_pct, 100):
            find = roller.equipment()
            full = game_data.items.armor[find.id].dur if find.id in game_data.items.armor else 0
            lines.append(SupplyLine(find.id, 1, full))
        drops.append(SupplyDrop(turn, tuple(lines)))
    return Drops(seed.canonical, level, tuple(drops))
