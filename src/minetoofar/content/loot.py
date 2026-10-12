"""The loot tables (data/loot.toml): what is found, where, and what dies with a monster."""

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

from minetoofar.content.balance import LEVELS
from minetoofar.content.gamedata import GameData, load_gamedata

Weights = tuple[tuple[str, int], ...]
CATEGORIES = ("consumable", "valuable", "equipment", "document")
EQUIPMENT = ("weapon", "armor", "trinket", "hat", "shield")
DOCUMENTS = ("memo", "coupon", "map")
ROOMS = ("mausoleum", "lair", "collapse", "gallery", "bunk", "flooded", "cemetery")
ANY_FIND = "*"  # a drop that is a document or a valuable, by the usual weights


class LootError(ValueError):
    pass


@dataclass(frozen=True)
class DropDef:
    item: str  # a valuable's id, or "*"
    max: int  # 1..max of them


@dataclass(frozen=True)
class LootTables:
    base_items: int
    per_level_items: int
    extra_per_vault: int
    document_cap: int
    condition_min_pct: int
    lair_documents: int
    categories: Weights
    consumables: Weights
    equipment: Weights
    documents: Weights
    rooms: Weights
    tiers: tuple[tuple[int, ...], ...]  # tiers[t - 1][level - 1]: percent chance of tier t
    drops: dict[str, DropDef]


def _int(where: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LootError(f"{where} must be an integer, got {value!r}")
    return value


def _weights(raw: dict[str, Any], name: str, allowed: tuple[str, ...]) -> Weights:
    table = raw.get(name)
    if not isinstance(table, dict):
        raise LootError(f"loot.toml is missing [{name}]")
    if set(table) != set(allowed):
        raise LootError(f"[{name}] needs exactly {allowed}, got {sorted(table)}")
    out = []
    for key in allowed:
        w = _int(f"{name}.{key}", table[key])
        if w < 0:
            raise LootError(f"{name}.{key} must not be negative")
        out.append((key, w))
    if sum(w for _, w in out) <= 0:
        raise LootError(f"[{name}] needs a positive weight somewhere")
    return tuple(out)


def parse_loot(text: str, data: GameData) -> LootTables:
    raw = tomllib.loads(text)
    required = {"loot", "categories", "consumables", "equipment", "documents", "rooms", "tiers"}
    if missing := sorted(required - set(raw)):
        raise LootError(f"loot.toml is missing sections {missing}")
    if unknown := sorted(set(raw) - required - {"drop"}):
        raise LootError(f"loot.toml: unknown sections {unknown}")
    params = raw["loot"]
    names = (
        "base_items", "per_level_items", "extra_per_vault", "document_cap",
        "condition_min_pct", "lair_documents",
    )  # fmt: skip
    if not isinstance(params, dict) or set(params) != set(names):
        raise LootError(f"[loot] needs exactly {names}")
    tiers_raw = raw["tiers"]
    if not isinstance(tiers_raw, dict) or set(tiers_raw) != {"tier1", "tier2", "tier3"}:
        raise LootError("[tiers] needs tier1, tier2, tier3")
    tiers = []
    for key in ("tier1", "tier2", "tier3"):
        row = tiers_raw[key]
        if not isinstance(row, list) or len(row) != LEVELS:
            raise LootError(f"tiers.{key} must list {LEVELS} (five) integers")
        tiers.append(tuple(_int(f"tiers.{key}", v) for v in row))
    for level in range(LEVELS):
        if sum(row[level] for row in tiers) != 100:
            raise LootError(f"tier percentages for level {level + 1} must sum to 100")
    drops: dict[str, DropDef] = {}
    for kind, entry in (raw.get("drop") or {}).items():
        if kind not in data.monsters:
            raise LootError(f"drop.{kind}: no such monster (nonesuch)")
        if not isinstance(entry, dict) or set(entry) != {"item", "max"}:
            raise LootError(f"drop.{kind} needs item and max")
        item, most = entry["item"], _int(f"drop.{kind}.max", entry["max"])
        if item != ANY_FIND and item not in data.items.valuables:
            raise LootError(f"drop.{kind}: no such valuable {item!r} (nonesuch)")
        if most < 1:
            raise LootError(f"drop.{kind}.max must be at least 1")
        drops[kind] = DropDef(item, most)
    num = {n: _int(f"loot.{n}", params[n]) for n in names}
    return LootTables(
        base_items=num["base_items"],
        per_level_items=num["per_level_items"],
        extra_per_vault=num["extra_per_vault"],
        document_cap=num["document_cap"],
        condition_min_pct=num["condition_min_pct"],
        lair_documents=num["lair_documents"],
        categories=_weights(raw, "categories", CATEGORIES),
        consumables=_weights(raw, "consumables", tuple(data.items.consumables)),
        equipment=_weights(raw, "equipment", EQUIPMENT),
        documents=_weights(raw, "documents", DOCUMENTS),
        rooms=_weights(raw, "rooms", ROOMS),
        tiers=tuple(tiers),
        drops=drops,
    )


@cache
def load_loot() -> LootTables:
    text = resources.files("minetoofar").joinpath("data", "loot.toml").read_text("utf-8")
    return parse_loot(text, load_gamedata())
