"""Classes, items, monsters, and statuses (data/*.toml), loaded through importlib.resources."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources

from minetoofar.content.tables import DataError, build, tables

RANKS = 5
STATS = ("str", "finesse")
ARMOR_WEIGHTS = ("light", "medium", "heavy")
FACTIONS = ("undead", "beast", "human")
BEHAVIORS = ("hunter", "skeleton", "phaser", "swarm", "eel", "badger", "overseer", "trapper")
ABILITY_KINDS = ("cleave", "coat", "dual_strike")
TRAP_EFFECTS = ("damage", "stun")
UPGRADE_RANK = 5  # the Rank at which every ability gets its upgrade (GDD 6.4)


@dataclass(frozen=True)
class ClassDef:
    name: str
    default_name: str
    signature: str
    ability: str
    blurb: str
    strength: int
    dexterity: int
    weapon: str
    offhand: str
    head: str
    body: str
    rank_hp: tuple[int, ...]
    rank_atk: tuple[int, ...]
    rank_dmg: tuple[int, ...]


@dataclass(frozen=True)
class WeaponDef:
    name: str
    dice_n: int
    dice_sides: int
    stat: str
    atk: int
    dmg: int
    cost: int
    two_handed: int


@dataclass(frozen=True)
class ArmorDef:
    name: str
    weight: str
    dr: int
    defense: int
    dur: int
    repair_rate: int


@dataclass(frozen=True)
class ShieldDef:
    name: str
    defense: int


@dataclass(frozen=True)
class HatDef:
    name: str
    defense: int
    trap_reduction: int  # taken off trap and cave-in damage


@dataclass(frozen=True)
class Items:
    weapons: Mapping[str, WeaponDef]
    armor: Mapping[str, ArmorDef]
    shields: Mapping[str, ShieldDef]
    hats: Mapping[str, HatDef]


@dataclass(frozen=True)
class MonsterDef:
    name: str
    faction: str
    hp: int
    atk: int
    defense: int
    dice_n: int
    dice_sides: int
    dmg: int
    dr: int
    move_cost: int
    attack_cost: int
    sight: int
    threat: int
    behavior: str  # which brain runs it (sim/behaviors.py)
    min_level: int  # first level it can spawn on
    weight: int  # spawn weight on a normal floor (0: never drawn)
    grave_weight: int  # ... on a graveyard floor


@dataclass(frozen=True)
class StatusDef:
    name: str
    duration_ticks: int
    delay_ticks: int  # added to the afflicted actor's ready_at when applied
    immune_ticks: int  # immunity after the status ends
    cost_pct: int  # action cost multiplier while active
    defense: int  # added to DEF while active (Soaked is -1)
    tick_ticks: int  # damage interval for tick statuses (Poisoned); 0 for none


@dataclass(frozen=True)
class AbilityDef:
    """One active ability. `value`, `charges`, and `cooldown_ticks` each have an `_up` twin that
    replaces it from Rank 5. What `value` means depends on `kind`: Cleave's ATK penalty, the
    Poisoned damage per tick for a coat, Dual Strike's bonus damage per hatchet."""

    name: str
    kind: str
    unlock_rank: int
    cooldown_ticks: int
    cooldown_ticks_up: int
    value: int
    value_up: int
    charges: int
    charges_up: int


@dataclass(frozen=True)
class TrapDef:
    name: str
    dice_n: int
    dice_sides: int
    dmg: int
    effect: str  # damage | stun


@dataclass(frozen=True)
class GameData:
    classes: Mapping[str, ClassDef]
    items: Items
    monsters: Mapping[str, MonsterDef]
    statuses: Mapping[str, StatusDef]
    abilities: Mapping[str, AbilityDef]
    traps: Mapping[str, TrapDef]


def _each[T](cls: type[T], raw: object, where: str) -> dict[str, T]:
    return {key: build(cls, table, f"{where}.{key}") for key, table in tables(raw, where).items()}


def _one_of(value: str, allowed: tuple[str, ...], what: str, where: str) -> None:
    if value not in allowed:
        raise DataError(f"{where}: {what} must be one of {allowed}, got {value!r}")


def _items(text: str) -> Items:
    raw = tomllib.loads(text)
    unknown = sorted(set(raw) - {"weapon", "armor", "shield", "hat"})
    if unknown:
        raise DataError(f"items: unknown kinds {unknown}")
    items = Items(
        _each(WeaponDef, raw.get("weapon", {}), "weapon"),
        _each(ArmorDef, raw.get("armor", {}), "armor"),
        _each(ShieldDef, raw.get("shield", {}), "shield"),
        _each(HatDef, raw.get("hat", {}), "hat"),
    )
    for key, weapon in items.weapons.items():
        _one_of(weapon.stat, STATS, "stat", f"weapon.{key}")
    for key, armor in items.armor.items():
        _one_of(armor.weight, ARMOR_WEIGHTS, "weight", f"armor.{key}")
    return items


def _abilities(text: str) -> dict[str, AbilityDef]:
    abilities = _each(AbilityDef, tomllib.loads(text), "ability")
    for key, a in abilities.items():
        _one_of(a.kind, ABILITY_KINDS, "kind", f"ability.{key}")
        if not 1 <= a.unlock_rank <= RANKS:
            raise DataError(f"ability.{key}.unlock_rank must be 1-{RANKS}, got {a.unlock_rank}")
    return abilities


def _classes(text: str, items: Items, abilities: Mapping[str, AbilityDef]) -> dict[str, ClassDef]:
    classes = _each(ClassDef, tomllib.loads(text), "class")
    for key, c in classes.items():
        for name in ("rank_hp", "rank_atk", "rank_dmg"):
            if len(getattr(c, name)) != RANKS:
                raise DataError(f"class.{key}.{name} must list {RANKS} integers")
        for slot, known in (
            (c.weapon, items.weapons),
            (c.body, items.armor),
            (c.head, items.hats),
        ):
            if slot not in known:
                raise DataError(f"class.{key}: no such item {slot!r}")
        if c.offhand and c.offhand not in items.shields and c.offhand not in items.weapons:
            raise DataError(f"class.{key}: no such item {c.offhand!r}")
        if c.ability not in abilities:
            raise DataError(f"class.{key}: no such ability {c.ability!r}")
    return classes


def _monsters(text: str) -> dict[str, MonsterDef]:
    monsters = _each(MonsterDef, tomllib.loads(text), "monster")
    for key, m in monsters.items():
        _one_of(m.faction, FACTIONS, "faction", f"monster.{key}")
        _one_of(m.behavior, BEHAVIORS, "behavior", f"monster.{key}")
    return monsters


def _traps(text: str) -> dict[str, TrapDef]:
    traps = _each(TrapDef, tomllib.loads(text), "trap")
    for key, t in traps.items():
        _one_of(t.effect, TRAP_EFFECTS, "effect", f"trap.{key}")
    return traps


def parse_gamedata(
    classes_text: str,
    items_text: str,
    monsters_text: str,
    statuses_text: str,
    abilities_text: str,
    traps_text: str,
) -> GameData:
    items = _items(items_text)
    abilities = _abilities(abilities_text)
    return GameData(
        _classes(classes_text, items, abilities),
        items,
        _monsters(monsters_text),
        _each(StatusDef, tomllib.loads(statuses_text), "status"),
        abilities,
        _traps(traps_text),
    )


@cache
def load_gamedata() -> GameData:
    """Read once per process; nothing mutates the tables."""
    base = resources.files("minetoofar").joinpath("data")
    names = ("classes", "items", "monsters", "statuses", "abilities", "traps")
    return parse_gamedata(*(base.joinpath(f"{n}.toml").read_text("utf-8") for n in names))
