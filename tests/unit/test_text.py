import pytest

from minetoofar.content.balance import LEVELS
from minetoofar.content.text import REQUIRED_LINES, TextError, load_text, parse_text
from minetoofar.core.grid import Tile

LEVELS_TOML = "".join(
    f'[[level]]\nname = "N{i}"\nwork_order = "W{i}"\n' for i in range(1, LEVELS + 1)
)
LOG_TOML = (
    "[lines]\n"
    + "".join(f'{key} = "text for {key}"\n' for key in sorted(REQUIRED_LINES))
    + "[tiles]\n"
    + "".join(f'{tile.name.lower()} = "a {tile.name}"\n' for tile in Tile)
)


def test_shipped_text_names_the_five_levels_from_the_gdd() -> None:
    levels = load_text().levels
    assert [lv.name for lv in levels] == [
        "Upper Galleries",
        "Stamp Mill and Assay Floor",
        "Flooded Drifts",
        "Old Timbers",
        "The Extra Level",
    ]
    assert levels[0].work_order == "Light Housekeeping"
    assert levels[4].work_order == "Final Walkthrough"


def test_shipped_text_has_every_required_line_and_tile_name() -> None:
    text = load_text()
    assert REQUIRED_LINES <= set(text.lines)
    assert all(text.tile_name(tile) for tile in Tile)


def test_line_fills_in_fields() -> None:
    text = parse_text(LEVELS_TOML, LOG_TOML.replace("text for welcome", "Order {number}"))
    assert text.line("welcome", number=3) == "Order 3"


def test_line_with_a_missing_field_fails_loudly() -> None:
    text = parse_text(LEVELS_TOML, LOG_TOML.replace("text for welcome", "Order {number}"))
    with pytest.raises(KeyError):
        text.line("welcome")


def test_unknown_line_key_fails_loudly() -> None:
    with pytest.raises(KeyError):
        parse_text(LEVELS_TOML, LOG_TOML).line("no_such_line")


def test_missing_required_line_is_rejected() -> None:
    with pytest.raises(TextError, match="door_opened"):
        parse_text(LEVELS_TOML, LOG_TOML.replace('door_opened = "text for door_opened"\n', ""))


def test_missing_tile_name_is_rejected() -> None:
    with pytest.raises(TextError, match="door_open"):
        parse_text(LEVELS_TOML, LOG_TOML.replace('door_open = "a DOOR_OPEN"\n', ""))


def test_wrong_number_of_levels_is_rejected() -> None:
    with pytest.raises(TextError, match="levels"):
        parse_text(LEVELS_TOML.replace('[[level]]\nname = "N5"\nwork_order = "W5"\n', ""), LOG_TOML)


def test_unknown_line_key_in_data_is_rejected() -> None:
    with pytest.raises(TextError, match="typo_line"):
        parse_text(LEVELS_TOML, LOG_TOML.replace("[tiles]", 'typo_line = "x"\n[tiles]'))


LOG_WIDTH = 76  # 80 columns less the log panel's border and padding
OWN_PANEL_PREFIXES = (
    "death_",
    "select_",
    "sheet_",
    "signature_",
    "ability_cleave",
    "ability_coat",
    "ability_dual",
)
DEATH_SCREEN_LINES = {
    k for k in REQUIRED_LINES if k.startswith(OWN_PANEL_PREFIXES)
}  # own panel, own width


def test_every_shipped_log_line_fits_the_log_panel_on_an_80_column_screen() -> None:
    text = load_text()
    fields = {
        "number": 5,
        "total": 5,
        "work_order": max((lv.work_order for lv in text.levels), key=len),
        "radius": 8,
        "name": "Gravedigger Skeleton",  # the longest monster name in the roster
        "target": "Gravedigger Skeleton",
        "attacker": "Gravedigger Skeleton",
        "killer": "Gravedigger Skeleton",
        "damage": 99,
        "armor": "Ballistic Vest (surplus)",
        "rank": 5,
        "turns": 30,
        "text": "x",
        "penalty": 2,
        "charges": 6,
        "bonus": 2,
        "min_w": 80,
        "min_h": 24,
        "w": 100,
        "h": 100,
    }
    for key in REQUIRED_LINES - {"too_small"} - DEATH_SCREEN_LINES:
        assert len(text.line(key, **fields)) <= LOG_WIDTH, key
