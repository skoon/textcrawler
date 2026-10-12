"""Balance tables, read through importlib.resources so source, wheel, and EXE behave alike."""

import tomllib
from dataclasses import dataclass, fields
from functools import cache
from importlib import resources
from typing import Any

LEVELS = 5


class BalanceError(ValueError):
    pass


@dataclass(frozen=True)
class LayoutParams:
    width: int
    height: int
    leaf_min_w: int
    leaf_min_h: int
    max_depth: int
    early_stop_from_depth: int
    early_stop_pct: int
    split_long_axis_pct: int
    room_margin: int
    room_min: int
    room_max_w: int
    room_max_h: int
    cave_fill_pct: int
    cave_iterations: int
    cave_wall_neighbors: int
    cave_min_pct: int
    cave_tries: int
    door_pct: int
    rooms_min: int
    rooms_max: int
    max_attempts: int
    extra_links_base: int
    extra_links_level_div: int


@dataclass(frozen=True)
class PlayParams:
    torch_radius: int
    move_cost: int
    door_cost: int
    wait_cost: int
    use_cost: int
    pickup_cost: int  # also dropping an item
    issue_kits: int  # Standard Issue tops the pack up to this many Patch-Up Kits ...
    issue_torches: int  # ... and this many Torches
    grave_fall_sides: int  # falling into an open grave hurts for 1 die of this many sides
    grave_climb_ticks: int  # ... and costs this long to climb out
    torch_brine_one_in: int  # a lit torch is lost 1 time in this many on entering Brine
    torch_crit_one_in: int  # ... and 1 time in this many when you take a critical hit


@dataclass(frozen=True)
class CombatParams:
    flank_bonus: int  # +to hit from the rear arc
    beast_bonus: int  # Tracker: damage against beasts
    backstab_dice: int  # Backstab adds this many dice ...
    backstab_sides: int  # ... of this many sides
    tracker_radius_sq: int  # sensing radius, squared (an integer circle)
    spot_radius_sq: int  # Rogue trap spotting, squared
    passive_spot_one_in: int  # others spot an adjacent trap 1 time in this many, per turn
    detergent_bonus: int  # Detergent Coat: damage against the undead


@dataclass(frozen=True)
class AiParams:
    wake_noise_one_in: int  # a sleeper that hears a noise wakes 1 time in this many
    buried_rise_radius_sq: int  # a buried Miner rises when the player is this close (squared)
    eel_resubmerge_ticks: int  # an Eel dives again after this long with nobody beside it
    eel_ambush_bonus: int  # +ATK on an ambush
    badger_flee_pct: int  # a Badger flees at this percent of its HP or less
    badger_burrow_ticks: int  # ... and digs away after this long out of sight
    clock_in_pct: int  # a Wraith's damaging hit Clocks you In this percent of the time
    phaser_wall_defense: int  # a Wraith inside a wall tile has this much more DEF
    swarm_max: int  # Vermin: +1 ATK per other Vermin beside the target, up to this
    aura_radius_sq: int  # Grimsby's Overtime aura reaches this far (squared)
    aura_ticks: int  # ... and lasts this long, renewed every turn
    overseer_min: int  # Grimsby holds off at least this far ...
    overseer_max: int  # ... and closes in beyond this
    trap_interval_ticks: int  # Vane lays a trap at most this often
    trap_sight_sq: int  # ... when he can see the player this close (squared)
    trapper_max_traps: int  # ... up to this many a level
    trapper_flee_ticks: int  # ... then retreats for this long
    speech_hit_cooldown: int  # a human taunts after landing a blow at most this often


@dataclass(frozen=True)
class NoiseParams:
    melee: int  # radius of the sound of a melee attack
    door: int  # ... of a door opening
    clang: int  # ... of a Skeleton's step or swing


@dataclass(frozen=True)
class ThemeParams:
    graveyard_pct: int  # chance a level is a graveyard floor (GDD 9.4)
    grimsby_pct: int  # chance its Rogue Human is Grimsby rather than Vane (GDD 9.6)


@dataclass(frozen=True)
class FeatureParams:
    flood_min_pct: int  # a Flooded Gallery is at least this percent Brine
    level3_flooded_min: int  # Level 3 guarantees extra Flooded Galleries ...
    level3_flooded_max: int  # ... this many at most
    collapse_pct: int  # chance a cave room is a Collapse (Rubble)
    bunk_pct: int  # chance any other room is a Bunk Room
    rubble_pct: int  # percent of a Collapse's floor that is Rubble
    cemetery_pct: int  # on a graveyard floor, chance a room is a Cemetery Plot
    gravestone_pct: int  # percent of a Cemetery Plot's interior that holds a gravestone
    grave_pct: int  # ... and an open grave
    monuments: int  # tombs in the Mausoleum


@dataclass(frozen=True)
class HumanParams:
    distance_pct: int  # the human's lair is at least this far along the way to the exit
    last_level_distance_pct: int  # ... and on the last level this far
    tic_one_in: int  # a human's tic is appended to 1 line in this many
    camp_traps: int  # traps already laid in Vane's camp


@dataclass(frozen=True)
class SpawnParams:
    budget_base: int
    budget_per_level: int
    graveyard_budget_pct: int  # a graveyard floor's budget is this percent of normal
    min_entry_distance: int  # path cost (10 per straight step) a spawn must be from the entry
    room_cap: int
    asleep_pct: int
    bunk_asleep_pct: int  # ... and in a Bunk Room
    grave_buried_pct: int  # a graveyard Miner starts buried in an open grave this often
    pack_min: int  # Cave Vermin come in packs of this many ...
    pack_max: int  # ... to this many


@dataclass(frozen=True)
class EconomyParams:
    base_fee: int
    hazard_premium: int  # graveyard floors only
    bounty: int  # the level's Rogue Human was defeated
    hazard_surcharge: int  # per trap triggered
    shoring_damage: int  # per Tripwire Charge, on top of the surcharge
    dropped_torch: int  # a lit Torch lost to Brine or a critical hit
    timecard_fee: int  # per Wraith Clock-In ...
    timecard_cap: int  # ... at most this much a level
    hazard_pay: int  # Stubborn invoked
    uniform_fee: int  # the Posthumous Pay Slip's Uniform Recovery Fee
    late_fee_pct: int  # of the balance carried forward, rounded up
    damage_waiver_cap: int  # Property Damage Waiver: incidentals up to this much
    lanyard_max: int  # Laminated Lanyard: the first incident line this size or less
    coupon_value: int
    level_score: int  # score per level cleared
    bounty_score: int  # ... and per bounty collected
    title_probationary: int  # the lowest score for each final title (GDD 8.8)
    title_valued: int
    title_senior: int
    title_employee: int


@dataclass(frozen=True)
class SupplyParams:
    none_weight: int  # a level rolls 0, 1 or 2 supply drops, at these weights
    one_weight: int
    two_weight: int
    trigger_min: int  # a drop lands on a turn in [trigger_min, trigger_max] ...
    trigger_max: int
    second_gap: int  # ... and the second at least this many turns after the first
    lines: int  # consumable lines in a crate
    qty_max: int  # each line is 1..qty_max of the item
    equipment_pct: int  # chance a crate also holds one piece of equipment
    handling_pct: int  # Expedited Handling on the taken lines, rounded up
    delivery_fee: int  # if anything is taken
    landing_radius: int  # a crate lands within this many tiles of the player
    price_t1: int  # equipment prices by tier
    price_t2: int
    price_t3: int


@dataclass(frozen=True)
class CheckinParams:
    desk_slots: int  # the Requisitions Desk offers this many items


@dataclass(frozen=True)
class Balance:
    layout: LayoutParams
    play: PlayParams
    combat: CombatParams
    ai: AiParams
    noise: NoiseParams
    theme: ThemeParams
    features: FeatureParams
    humans: HumanParams
    spawns: SpawnParams
    economy: EconomyParams
    supply: SupplyParams
    checkin: CheckinParams
    cavern_pct: tuple[int, ...]
    trap_counts: tuple[int, ...]  # hidden traps placed on each level


def _check_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BalanceError(f"{name} must be an integer, got {value!r}")
    return value


def _section[T](raw: dict[str, Any], name: str, cls: type[T]) -> T:
    table = raw.get(name, {})
    names = [f.name for f in fields(cls)]  # type: ignore[arg-type]
    if set(table) - set(names):
        raise BalanceError(f"unknown {name} keys: {sorted(set(table) - set(names))}")
    missing = [n for n in names if n not in table]
    if missing:
        raise BalanceError(f"missing {name} keys: {missing}")
    return cls(**{n: _check_int(f"{name}.{n}", table[n]) for n in names})


def parse_balance(text: str) -> Balance:
    raw = tomllib.loads(text)
    unknown = set(raw) - {
        "layout",
        "play",
        "combat",
        "ai",
        "noise",
        "theme",
        "features",
        "humans",
        "spawns",
        "economy",
        "supply",
        "checkin",
        "levels",
    }
    if unknown:
        raise BalanceError(f"unknown top-level keys: {sorted(unknown)}")
    levels = raw.get("levels", {})
    per_level = {}
    for key in ("cavern_pct", "trap_counts"):
        listed = levels.get(key)
        if not isinstance(listed, list) or len(listed) != LEVELS:
            raise BalanceError(f"levels.{key} must list {LEVELS} integers")
        per_level[key] = tuple(_check_int(f"levels.{key}", v) for v in listed)
    return Balance(
        _section(raw, "layout", LayoutParams),
        _section(raw, "play", PlayParams),
        _section(raw, "combat", CombatParams),
        _section(raw, "ai", AiParams),
        _section(raw, "noise", NoiseParams),
        _section(raw, "theme", ThemeParams),
        _section(raw, "features", FeatureParams),
        _section(raw, "humans", HumanParams),
        _section(raw, "spawns", SpawnParams),
        _section(raw, "economy", EconomyParams),
        _section(raw, "supply", SupplyParams),
        _section(raw, "checkin", CheckinParams),
        per_level["cavern_pct"],
        per_level["trap_counts"],
    )


@cache
def load_balance() -> Balance:
    """Read once per process: the tables are frozen, so every caller can share them."""
    text = resources.files("minetoofar").joinpath("data", "balance.toml").read_text("utf-8")
    return parse_balance(text)
