"""The Requisitions Desk catalog (data/desk.toml)."""

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources

from minetoofar.content.gamedata import GameData, load_gamedata
from minetoofar.content.tables import DataError, build

EFFECTS = (
    "bundle", "weapon_dmg", "weapon_atk", "plating", "item", "max_hp", "repair_plan",
    "damage_waiver", "hazard_waiver",
)  # fmt: skip
NEEDS_AN_ITEM = ("bundle", "item")


class DeskError(DataError):
    pass


@dataclass(frozen=True)
class DeskItem:
    name: str
    blurb: str
    price: int
    weight: int
    effect: str
    item: str
    qty: int
    value: int
    cap: int


def parse_desk(text: str, data: GameData) -> dict[str, DeskItem]:
    raw = tomllib.loads(text)
    catalog: dict[str, DeskItem] = {}
    for key, table in raw.items():
        try:
            item = build(DeskItem, table, f"desk.{key}")
        except DataError as err:
            raise DeskError(str(err)) from err
        if item.effect not in EFFECTS:
            raise DeskError(f"desk.{key}: effect must be one of {EFFECTS}, got {item.effect!r}")
        if item.weight < 0 or item.price < 0:
            raise DeskError(f"desk.{key}: price and weight must not be negative")
        if item.effect in NEEDS_AN_ITEM and item.item not in data.items.category_of_all():
            raise DeskError(f"desk.{key}: no such item {item.item!r} (nonesuch)")
        catalog[key] = item
    if sum(i.effect == "bundle" for i in catalog.values()) < 2:
        raise DeskError("the desk needs at least two bundles to choose slot 1 from")
    return catalog


@cache
def load_desk() -> dict[str, DeskItem]:
    text = resources.files("minetoofar").joinpath("data", "desk.toml").read_text("utf-8")
    return parse_desk(text, load_gamedata())
