import pytest

from minetoofar.core.grid import Tile
from minetoofar.ui.glyphs import (
    ASCII,
    GLYPH_TABLE,
    UNICODE,
    auto_glyph_name,
    glyph_set,
    hp_bar,
    render_cells,
    wall_autotile,
)
from tests.helpers import grid_from_rows

GDD_AUTOTILE = "▪║═╚║║╔╠═╝═╩╗╣╦╬"  # GDD 5.4, masks 0..15 with N=1 E=2 S=4 W=8


@pytest.mark.parametrize("mask", range(16))
def test_autotile_matches_gdd_table(mask: int) -> None:
    assert wall_autotile(mask) == GDD_AUTOTILE[mask]


def render(rows: list[str], y: int, name: str) -> str:
    return "".join(ch for ch, _ in render_cells(grid_from_rows(rows), y, glyph_set(name)))


def test_unicode_room_gets_box_drawing_walls_and_dot_floor() -> None:
    rows = ["#####", "#...#", "#####"]
    assert [render(rows, y, "unicode") for y in range(3)] == ["╔═══╗", "║···║", "╚═══╝"]


def test_ascii_room_uses_plain_characters() -> None:
    rows = ["#####", "#...#", "#####"]
    assert [render(rows, y, "ascii") for y in range(3)] == ["#####", "#...#", "#####"]


def test_doors_count_as_wall_when_picking_a_wall_piece() -> None:
    assert render(["  #+"], 0, "unicode") == "  ═+"  # not an isolated ▪
    assert render(["##+##", "#...#", "#####"], 0, "unicode") == "╔═+═╗"


def test_special_tiles_in_both_sets() -> None:
    rows = ["%,<>+"]
    assert render(rows, 0, "unicode") == "▒·▲▼+"
    assert render(rows, 0, "ascii") == "#.<>+"


def test_solid_renders_blank() -> None:
    assert render(["  ."], 0, "unicode") == "  ·"


def test_cells_carry_their_tile_for_styling() -> None:
    cells = render_cells(grid_from_rows(["#.>"]), 0, UNICODE)
    assert [t for _, t in cells] == [Tile.WALL, Tile.FLOOR, Tile.EXIT]


def test_ascii_set_is_pure_ascii() -> None:
    assert all(ch.isascii() for _, _, _, ch in GLYPH_TABLE)
    assert all(ch.isascii() for ch in ASCII.tiles.values())


def test_glyph_table_is_single_cell_and_unique_per_name() -> None:
    names = [name for _, name, _, _ in GLYPH_TABLE]
    assert len(names) == len(set(names))
    assert all(len(u) == 1 and len(a) == 1 for _, _, u, a in GLYPH_TABLE)


def test_glyph_table_matches_gdd_actors() -> None:
    table = {name: (u, a) for _, name, u, a in GLYPH_TABLE}
    assert table["Player"] == ("@", "@")
    assert table["Gravedigger Skeleton"] == ("Ξ", "S")
    assert table["Timecard Wraith"] == ("Ω", "W")
    assert table["Prospector Vane"] == ("Π", "V")


def test_unknown_glyph_set_is_rejected() -> None:
    with pytest.raises(ValueError):
        glyph_set("emoji")


@pytest.mark.parametrize(
    ("platform", "env", "encoding", "expected"),
    [
        ("win32", {"WT_SESSION": "abc"}, "utf-8", "unicode"),
        ("win32", {"TERM_PROGRAM": "vscode"}, "utf-8", "unicode"),
        ("win32", {}, "utf-8", "ascii"),  # classic console: play safe
        ("linux", {"TERM": "xterm-256color"}, "utf-8", "unicode"),
        ("linux", {"TERM": "dumb"}, "utf-8", "ascii"),
        ("linux", {"TERM": "xterm"}, "cp1252", "ascii"),
        ("linux", {}, None, "ascii"),
    ],
)
def test_auto_detection(
    platform: str, env: dict[str, str], encoding: str | None, expected: str
) -> None:
    assert auto_glyph_name(platform, env, encoding) == expected


def test_open_door_has_its_own_glyph_in_both_sets() -> None:
    assert render(["#/#"], 0, "unicode")[1] == "/"
    assert render(["#/#"], 0, "ascii")[1] == "/"


def test_open_doors_join_the_wall_line_like_closed_ones() -> None:
    assert render(["#/#"], 0, "unicode") == "═/═"


def test_autotile_ignores_neighbours_the_player_has_not_seen() -> None:
    grid = grid_from_rows(["###"])
    everything = bytes([1, 1, 1])
    only_middle = bytes([0, 1, 0])
    assert "".join(c for c, _ in render_cells(grid, 0, UNICODE, everything)) == "═══"
    assert render_cells(grid, 0, UNICODE, only_middle)[1][0] == "▪"
    assert render_cells(grid, 0, UNICODE)[1][0] == "═"  # no fog mask: all neighbours count


@pytest.mark.parametrize(
    ("hp", "maximum", "unicode_bar"),
    [(30, 30, "████████████"), (15, 30, "██████░░░░░░"), (1, 30, "█░░░░░░░░░░░"),
     (0, 30, "░░░░░░░░░░░░"), (29, 30, "████████████")],
)  # fmt: skip
def test_hp_bar_rounds_up_so_any_life_shows_a_cell(hp: int, maximum: int, unicode_bar: str) -> None:
    assert hp_bar(hp, maximum, 12, UNICODE) == unicode_bar
    assert hp_bar(hp, maximum, 12, ASCII) == unicode_bar.replace("█", "#").replace("░", "-")


def test_monsters_have_a_glyph_in_both_sets() -> None:
    assert UNICODE.monsters["shambling_miner"] == "M" and ASCII.monsters["shambling_miner"] == "M"


def test_traps_and_vermin_have_glyphs_in_both_sets() -> None:
    assert (UNICODE.trap, UNICODE.trap_off, UNICODE.sensed) == ("Δ", "×", None)
    assert (ASCII.trap, ASCII.trap_off, ASCII.sensed) == ("^", "x", "?")
    assert UNICODE.monsters["cave_vermin"] == "ν" and ASCII.monsters["cave_vermin"] == "v"


def test_both_sets_draw_every_kind_of_tile() -> None:
    for glyphs in (UNICODE, ASCII):
        assert set(glyphs.tiles) == set(Tile), glyphs.name


def test_terrain_glyphs_match_the_gdd_table() -> None:
    expected = {
        Tile.BRINE: ("≈", "~"), Tile.RUBBLE: ("∴", ":"), Tile.GRAVESTONE: ("†", "T"),
        Tile.MONUMENT: ("‡", "H"), Tile.OPEN_GRAVE: ("∪", "u"),
    }  # fmt: skip
    for tile, (uni, asc) in expected.items():
        assert UNICODE.tiles[tile] == uni and ASCII.tiles[tile] == asc


def test_every_monster_in_the_roster_has_a_glyph_in_both_sets() -> None:
    from minetoofar.content.gamedata import load_gamedata

    roster = set(load_gamedata().monsters)
    assert set(UNICODE.monsters) == roster and set(ASCII.monsters) == roster


def test_monster_glyphs_match_gdd_5_4() -> None:
    expected = {
        "shambling_miner": ("M", "M"), "gravedigger_skeleton": ("Ξ", "S"),
        "timecard_wraith": ("Ω", "W"), "cave_vermin": ("ν", "v"), "blind_ore_eel": ("ε", "e"),
        "gem_badger": ("β", "b"), "foreman_grimsby": ("Γ", "G"), "prospector_vane": ("Π", "V"),
    }  # fmt: skip
    for kind, (uni, asc) in expected.items():
        assert UNICODE.monsters[kind] == uni and ASCII.monsters[kind] == asc
