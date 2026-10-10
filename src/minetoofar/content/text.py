"""Player-facing text tables (data/text/*.toml): level names, log lines, tile names."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources

from minetoofar.content.balance import LEVELS
from minetoofar.core.grid import Tile

# Every log line the UI may ask for; the loader insists on exactly this set so a typo in the
# data file fails at load time instead of mid-game.
REQUIRED_LINES = frozenset(
    {
        "welcome",
        "door_opened",
        "blocked_wall",
        "blocked_corner",
        "blocked_door",
        "on_exit",
        "descend_none",
        "descend_last",
        "brine_prompt",
        "torch_lit",
        "torch_snuffed",
        "quit_prompt",
        "too_small",
        "look_unexplored",
        "look_remembered",
        "you_hit",
        "you_crit",
        "you_miss",
        "they_hit",
        "they_crit",
        "they_miss",
        "you_killed",
        "died",
        "stubborn",
        "noticed",
        "spotted",
        "rank_set",
        "armor_broken",
        "death_title",
        "death_associate",
        "death_cause",
        "death_order",
        "death_turns",
        "death_seed",
        "death_regret",
        "death_keys",
        "you_backstab",
        "ability_used",
        "refused_locked",
        "refused_cooldown",
        "refused_no_target",
        "refused_not_rogue",
        "refused_no_trap",
        "status_poisoned",
        "poison_tick",
        "trap_spotted",
        "trap_triggered",
        "trap_disarmed",
        "blocked_trap",
        "disarm_prompt",
        "step_prompt",
        "select_title",
        "select_keys",
        "sheet_title",
        "signature_stubborn",
        "signature_backstab",
        "signature_tracker",
        "ability_cleave",
        "ability_coat",
        "ability_dual_strike",
        "spoke",
        "rose",
        "surfaced",
        "fled",
        "burrowed",
        "torch_dropped",
        "grave_fall",
        "status_you_stunned",
        "status_you_clocked_in",
        "trap_stunned",
        "blocked_occupied",
    }
)


class TextError(ValueError):
    pass


@dataclass(frozen=True)
class LevelInfo:
    name: str
    work_order: str


@dataclass(frozen=True)
class Text:
    levels: tuple[LevelInfo, ...]
    lines: Mapping[str, str]
    tiles: Mapping[str, str]

    def line(self, key: str, **fields: object) -> str:
        return self.lines[key].format(**fields)

    def tile_name(self, tile: Tile) -> str:
        return self.tiles[tile.name.lower()]


def _strings(table: object, what: str) -> dict[str, str]:
    if not isinstance(table, dict) or not all(isinstance(v, str) for v in table.values()):
        raise TextError(f"{what} must be a table of strings")
    return dict(table)


def _level(entry: object) -> LevelInfo:
    fields = _strings(entry, "level")
    if set(fields) != {"name", "work_order"}:
        raise TextError(f"each level needs exactly name and work_order, got {sorted(fields)}")
    return LevelInfo(fields["name"], fields["work_order"])


def parse_text(levels_text: str, log_text: str) -> Text:
    raw_levels = tomllib.loads(levels_text).get("level", [])
    if len(raw_levels) != LEVELS:
        raise TextError(f"levels.toml must define {LEVELS} levels, found {len(raw_levels)}")
    levels = tuple(_level(entry) for entry in raw_levels)
    log = tomllib.loads(log_text)
    lines = _strings(log.get("lines"), "[lines]")
    if set(lines) != REQUIRED_LINES:
        diff = sorted(set(lines) ^ REQUIRED_LINES)
        raise TextError(f"log.toml [lines] has missing or unknown keys: {diff}")
    tiles = _strings(log.get("tiles"), "[tiles]")
    wanted = {tile.name.lower() for tile in Tile}
    if set(tiles) != wanted:
        raise TextError(
            f"log.toml [tiles] has missing or unknown keys: {sorted(set(tiles) ^ wanted)}"
        )
    return Text(levels, lines, tiles)


def load_text() -> Text:
    base = resources.files("minetoofar").joinpath("data", "text")
    return parse_text(
        base.joinpath("levels.toml").read_text("utf-8"),
        base.joinpath("log.toml").read_text("utf-8"),
    )
