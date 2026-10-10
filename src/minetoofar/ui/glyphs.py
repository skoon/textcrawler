"""Glyph sets (GDD 5.4). Pure functions: nothing here imports Textual, so tests need no terminal."""

from collections.abc import Mapping
from dataclasses import dataclass

from minetoofar.core.grid import Grid, Tile

# Wall piece by neighbour mask, N=1 E=2 S=4 W=8.
_AUTOTILE = "▪║═╚║║╔╠═╝═╩╗╣╦╬"


def wall_autotile(mask: int) -> str:
    return _AUTOTILE[mask]


@dataclass(frozen=True)
class GlyphSet:
    name: str
    tiles: Mapping[Tile, str]
    autotile: bool
    hp_full: str
    hp_empty: str
    monsters: Mapping[str, str]  # monster kind -> glyph
    trap: str
    trap_off: str  # a disarmed trap
    sensed: str | None  # glyph for every sensed enemy; None keeps each monster's own glyph


UNICODE = GlyphSet(
    "unicode",
    {
        Tile.SOLID: " ", Tile.WALL: "#", Tile.ROCK: "▒", Tile.FLOOR: "·",
        Tile.CAVE_FLOOR: "·", Tile.DOOR: "+", Tile.ENTRY: "▲", Tile.EXIT: "▼",
        Tile.DOOR_OPEN: "/", Tile.BRINE: "≈", Tile.RUBBLE: "∴", Tile.GRAVESTONE: "†",
        Tile.MONUMENT: "‡", Tile.OPEN_GRAVE: "∪",
    },
    autotile=True,
    hp_full="█",
    hp_empty="░",
    monsters={
        "shambling_miner": "M", "gravedigger_skeleton": "Ξ", "timecard_wraith": "Ω",
        "cave_vermin": "ν", "blind_ore_eel": "ε", "gem_badger": "β",
        "foreman_grimsby": "Γ", "prospector_vane": "Π",
    },
    trap="Δ",
    trap_off="×",
    sensed=None,
)  # fmt: skip
ASCII = GlyphSet(
    "ascii",
    {
        Tile.SOLID: " ", Tile.WALL: "#", Tile.ROCK: "#", Tile.FLOOR: ".",
        Tile.CAVE_FLOOR: ".", Tile.DOOR: "+", Tile.ENTRY: "<", Tile.EXIT: ">",
        Tile.DOOR_OPEN: "/", Tile.BRINE: "~", Tile.RUBBLE: ":", Tile.GRAVESTONE: "T",
        Tile.MONUMENT: "H", Tile.OPEN_GRAVE: "u",
    },
    autotile=False,
    hp_full="#",
    hp_empty="-",
    monsters={
        "shambling_miner": "M", "gravedigger_skeleton": "S", "timecard_wraith": "W",
        "cave_vermin": "v", "blind_ore_eel": "e", "gem_badger": "b",
        "foreman_grimsby": "G", "prospector_vane": "V",
    },
    trap="^",
    trap_off="x",
    sensed="?",
)  # fmt: skip
_SETS = {"unicode": UNICODE, "ascii": ASCII}


def glyph_set(name: str) -> GlyphSet:
    try:
        return _SETS[name]
    except KeyError:
        raise ValueError(f"unknown glyph set {name!r}; choose unicode or ascii") from None


def auto_glyph_name(platform: str, env: Mapping[str, str], encoding: str | None) -> str:
    """Unicode when the output is UTF-8 and the terminal is likely modern; otherwise ASCII."""
    if not encoding or encoding.lower().replace("_", "-") not in ("utf-8", "utf8"):
        return "ascii"
    if env.get("TERM") == "dumb":
        return "ascii"
    if platform == "win32" and not (env.get("WT_SESSION") or env.get("TERM_PROGRAM")):
        return "ascii"  # classic console: may lack glyphs, ASCII always works
    return "unicode"


def hp_bar(hp: int, maximum: int, width: int, glyphs: GlyphSet) -> str:
    """A bar of `width` cells; any hit point left shows at least one filled cell."""
    filled = 0 if hp <= 0 else (hp * width + maximum - 1) // maximum
    return glyphs.hp_full * filled + glyphs.hp_empty * (width - filled)


_WALLISH = frozenset({Tile.WALL, Tile.DOOR, Tile.DOOR_OPEN})
_NEIGHBOURS = ((1, (0, -1)), (2, (1, 0)), (4, (0, 1)), (8, (-1, 0)))


def render_cells(
    grid: Grid, y: int, glyphs: GlyphSet, known: bytes | None = None
) -> list[tuple[str, Tile]]:
    """One map row as (character, tile) pairs; the tile lets the caller pick a color.

    With `known` (one byte per tile, 0 = never seen) a wall piece joins only neighbours the
    player has seen, so the autotile never leaks the shape of unexplored rock (GDD 5.4).
    """
    row: list[tuple[str, Tile]] = []
    for x in range(grid.width):
        tile = grid.get(x, y)
        if tile == Tile.WALL and glyphs.autotile:
            mask = 0
            for bit, (dx, dy) in _NEIGHBOURS:
                nx, ny = x + dx, y + dy
                if grid.in_bounds(nx, ny) and grid.get(nx, ny) in _WALLISH:
                    if known is None or known[ny * grid.width + nx]:
                        mask |= bit
            row.append((wall_autotile(mask), tile))
        else:
            row.append((glyphs.tiles[tile], tile))
    return row


# (category, name, unicode, ascii): the audit list behind --glyph-test (GDD 5.4).
GLYPH_TABLE: tuple[tuple[str, str, str, str], ...] = (
    ("terrain", "Floor", "·", "."),
    ("terrain", "Natural rock", "▒", "#"),
    ("terrain", "Door, closed", "+", "+"),
    ("terrain", "Door, open", "/", "/"),
    ("terrain", "Entry stairs", "▲", "<"),
    ("terrain", "Down Shaft", "▼", ">"),
    ("terrain", "Brine", "≈", "~"),
    ("terrain", "Rubble", "∴", ":"),
    ("terrain", "Support beam", "╫", "|"),
    ("terrain", "Trap, revealed", "Δ", "^"),
    ("terrain", "Trap, disarmed", "×", "x"),
    ("terrain", "Supply crate", "■", "="),
    ("terrain", "Gravestone", "†", "T"),
    ("terrain", "Monument", "‡", "H"),
    ("terrain", "Open grave", "∪", "u"),
    ("item", "Weapon", "↑", ")"),
    ("item", "Armor", "[", "["),
    ("item", "Trinket", "°", '"'),
    ("item", "Consumable", "¡", "!"),
    ("item", "Silver", "¤", "$"),
    ("item", "Gem", "◊", "*"),
    ("item", "Document", "≡", "?"),
    ("actor", "Player", "@", "@"),
    ("actor", "Shambling Miner", "M", "M"),
    ("actor", "Gravedigger Skeleton", "Ξ", "S"),
    ("actor", "Timecard Wraith", "Ω", "W"),
    ("actor", "Cave Vermin", "ν", "v"),
    ("actor", "Blind Ore-Eel", "ε", "e"),
    ("actor", "Gem Badger", "β", "b"),
    ("actor", "Foreman Grimsby", "Γ", "G"),
    ("actor", "Prospector Vane", "Π", "V"),
    ("ui", "Wall piece", "═", "#"),
    ("ui", "HP full", "█", "#"),
    ("ui", "HP empty", "░", "-"),
)
