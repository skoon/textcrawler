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
        "title_name",
        "title_tagline",
        "title_continue",
        "title_new",
        "title_quit",
        "title_confirm_new",
        "title_no_save",
        "help_title",
        "help_text",
        "title_records",
        "records_title",
        "records_none",
        "records_entry",
        "records_victory",
        "records_death",
        "records_more",
        "records_back",
        "menu_title",
        "menu_save",
        "menu_back",
        "menu_replace_prompt",
        "confirm_keys",
        "save_failed",
        "resumed",
        "record_failed",
        "supply_inbound",
        "supply_taken",
        "refused_no_crate",
        "refused_nothing_taken",
        "invoice_title",
        "invoice_subtotal",
        "invoice_handling",
        "invoice_delivery",
        "invoice_total",
        "invoice_keys",
        "invoice_empty",
        "report_title",
        "report_order",
        "report_closed",
        "report_undead",
        "report_beasts",
        "report_human",
        "report_at_large",
        "report_retrieved",
        "report_valuables",
        "report_turns",
        "report_wellness",
        "report_issue",
        "report_issue_none",
        "report_promotion",
        "report_unlock",
        "report_keys",
        "memo_title",
        "memo_keys",
        "desk_title",
        "desk_good",
        "desk_hold",
        "desk_hold_note",
        "desk_repair_note",
        "desk_keys",
        "desk_sold",
        "desk_bought",
        "desk_refused_on_hold",
        "desk_refused_sold",
        "desk_refused_poor",
        "desk_refused_no_room",
        "desk_refused_capped",
        "desk_refused_have_it",
        "item_picked",
        "valuable",
        "item_used",
        "item_used_prepaid",
        "healed",
        "item_dropped",
        "equipped",
        "see_here",
        "torch_burned_out",
        "document_read",
        "human_defeated",
        "refused_nothing_here",
        "refused_pack_full",
        "refused_no_item",
        "refused_not_usable",
        "refused_full_hp",
        "refused_not_equipment",
        "refused_not_light",
        "refused_two_handed",
        "refused_no_torch",
        "refused_already_lit",
        "inventory_title",
        "inventory_empty",
        "inventory_keys",
        "menu_equip",
        "menu_use",
        "menu_drop",
        "document_title",
        "document_keys",
        "slip_title",
        "slip_posthumous_title",
        "slip_head",
        "slip_order",
        "slip_associate",
        "slip_number",
        "slip_gross",
        "slip_gross_total",
        "slip_adjustments",
        "slip_adjusted_total",
        "slip_net",
        "slip_wallet",
        "slip_owing",
        "slip_waived",
        "slip_thanks",
        "slip_thanks_posthumous",
        "slip_keys",
        "slip_keys_coupon",
        "slip_coupon_applied",
        "death_score",
        "death_final_title",
        "title_terminated",
        "title_probationary",
        "title_valued",
        "title_senior",
        "title_employee",
        "review_title",
        "review_surface",
        "review_keys",
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
