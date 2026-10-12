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
CONSUMABLE_EFFECTS = ("heal", "light", "status")
TIERS = 3
SHINES = ("silver", "gem")
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
    tier: int
    light: int  # 1: may be held in the off hand
    noise: int  # radius of the sound of a blow; 0 for an ordinary one
    stuns: int  # 1: a critical hit stuns


@dataclass(frozen=True)
class ArmorDef:
    name: str
    weight: str
    dr: int
    defense: int
    dur: int
    repair_rate: int
    tier: int


@dataclass(frozen=True)
class ShieldDef:
    name: str
    defense: int
    tier: int


@dataclass(frozen=True)
class HatDef:
    name: str
    defense: int
    trap_reduction: int  # taken off trap and cave-in damage
    lamp: int  # light radius the hat gives
    tier: int


@dataclass(frozen=True)
class TrinketDef:
    name: str
    atk: int
    hp: int  # added to max HP
    waives: int  # 1: the first small incident line each level is waived
    tier: int


@dataclass(frozen=True)
class ConsumableDef:
    name: str
    price: int  # list price in gold
    carry: int  # most you can hold
    effect: str  # heal | light | status
    value: int  # hit points healed, ticks of burn time, or ticks of the status
    status: str  # the status a "status" item applies; empty otherwise


@dataclass(frozen=True)
class ValuableDef:
    name: str
    credit: int  # gold of Salvage Credit
    weight: int  # loot weight
    shine: str  # silver | gem: which glyph it is drawn with


def found_charge(item: ConsumableDef) -> int:
    """What a found (reclaimed stock) consumable bills when used: half the list price, up."""
    return -(-item.price // 2)


@dataclass(frozen=True)
class Items:
    weapons: Mapping[str, WeaponDef]
    armor: Mapping[str, ArmorDef]
    shields: Mapping[str, ShieldDef]
    hats: Mapping[str, HatDef]
    trinkets: Mapping[str, TrinketDef]
    consumables: Mapping[str, ConsumableDef]
    valuables: Mapping[str, ValuableDef]

    def _tables(self) -> tuple[tuple[str, Mapping[str, object]], ...]:
        return (
            ("weapon", self.weapons), ("armor", self.armor), ("shield", self.shields),
            ("hat", self.hats), ("trinket", self.trinkets),
            ("consumable", self.consumables), ("valuable", self.valuables),
        )  # fmt: skip

    def category_of_all(self) -> frozenset[str]:
        """Every item id there is."""
        return frozenset(k for _, table in self._tables() for k in table)

    def name(self, item_id: str) -> str:
        for _, table in self._tables():
            if item_id in table:
                return str(table[item_id].name)  # type: ignore[attr-defined]
        raise KeyError(item_id)

    def category(self, item_id: str) -> str:
        """weapon | armor | shield | hat | trinket | consumable | valuable."""
        for name, table in self._tables():
            if item_id in table:
                return name
        raise KeyError(item_id)


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
    cave_in: int  # 1: a cave-in, which adds Shoring Damage to the pay slip


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


def _flag(value: int, what: str, where: str) -> None:
    if value not in (0, 1):
        raise DataError(f"{where}: {what} must be 0 or 1, got {value}")


def _one_of(value: str, allowed: tuple[str, ...], what: str, where: str) -> None:
    if value not in allowed:
        raise DataError(f"{where}: {what} must be one of {allowed}, got {value!r}")


def _items(text: str) -> Items:
    raw = tomllib.loads(text)
    kinds = {"weapon", "armor", "shield", "hat", "trinket", "consumable", "valuable"}
    unknown = sorted(set(raw) - kinds)
    if unknown:
        raise DataError(f"items: unknown kinds {unknown}")
    items = Items(
        _each(WeaponDef, raw.get("weapon", {}), "weapon"),
        _each(ArmorDef, raw.get("armor", {}), "armor"),
        _each(ShieldDef, raw.get("shield", {}), "shield"),
        _each(HatDef, raw.get("hat", {}), "hat"),
        _each(TrinketDef, raw.get("trinket", {}), "trinket"),
        _each(ConsumableDef, raw.get("consumable", {}), "consumable"),
        _each(ValuableDef, raw.get("valuable", {}), "valuable"),
    )
    seen: set[str] = set()
    for name, table in items._tables():
        for key in table:
            if key in seen:
                raise DataError(f"{name}.{key}: duplicate item id")
            seen.add(key)
    for key, weapon in items.weapons.items():
        where = f"weapon.{key}"
        _one_of(weapon.stat, STATS, "stat", where)
        for flag in ("two_handed", "light", "stuns"):
            _flag(getattr(weapon, flag), flag, where)
        if weapon.two_handed and weapon.light:
            raise DataError(f"{where}: a two-handed weapon cannot be light")
    for key, armor in items.armor.items():
        _one_of(armor.weight, ARMOR_WEIGHTS, "weight", f"armor.{key}")
    for name, table in items._tables()[:5]:
        for key, item in table.items():
            if not 1 <= item.tier <= TIERS:  # type: ignore[attr-defined]
                raise DataError(f"{name}.{key}: tier must be 1-{TIERS}")
    for key, trinket in items.trinkets.items():
        _flag(trinket.waives, "waives", f"trinket.{key}")
    for key, valuable in items.valuables.items():
        _one_of(valuable.shine, SHINES, "shine", f"valuable.{key}")
    for key, item in items.consumables.items():
        _one_of(item.effect, CONSUMABLE_EFFECTS, "effect", f"consumable.{key}")
        if (item.effect == "status") != bool(item.status):
            raise DataError(f"consumable.{key}: only a status item names a status")
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
        _flag(t.cave_in, "cave_in", f"trap.{key}")
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
    statuses = _each(StatusDef, tomllib.loads(statuses_text), "status")
    for key, item in items.consumables.items():
        if item.status and item.status not in statuses:
            raise DataError(f"consumable.{key}: no such status {item.status!r}")
    return GameData(
        _classes(classes_text, items, abilities),
        items,
        _monsters(monsters_text),
        statuses,
        abilities,
        _traps(traps_text),
    )


@cache
def load_gamedata() -> GameData:
    """Read once per process; nothing mutates the tables."""
    base = resources.files("minetoofar").joinpath("data")
    names = ("classes", "items", "monsters", "statuses", "abilities", "traps")
    return parse_gamedata(*(base.joinpath(f"{n}.toml").read_text("utf-8") for n in names))
