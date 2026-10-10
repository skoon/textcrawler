"""Default key bindings (GDD 4.1): raw Textual keys in, game commands or UI actions out."""

from enum import Enum, auto

from minetoofar.sim.events import Command, Move, Run, ToggleTorch, UseAbility, Wait


class UiAction(Enum):
    LOOK = auto()
    QUIT = auto()
    GLYPHS = auto()
    REDRAW = auto()
    SHEET = auto()
    DESCEND = auto()
    SKIP = auto()  # debug: jump to the next level from anywhere


# direction -> keys that step that way (arrow cluster, numpad digit, vi key)
_STEP_KEYS: dict[tuple[int, int], tuple[str, ...]] = {
    (0, -1): ("up", "8", "k"),
    (1, -1): ("pageup", "9", "u"),
    (1, 0): ("right", "6", "l"),
    (1, 1): ("pagedown", "3", "n"),
    (0, 1): ("down", "2", "j"),
    (-1, 1): ("end", "1", "b"),
    (-1, 0): ("left", "4", "h"),
    (-1, -1): ("home", "7", "y"),
}
_SHIFT_ARROWS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

BINDINGS: dict[str, Command | UiAction] = {
    "5": Wait(), "space": Wait(), ".": Wait(), "x": UiAction.LOOK, "Q": UiAction.QUIT,
    "f2": UiAction.GLYPHS, "ctrl+l": UiAction.REDRAW, "t": ToggleTorch(), "a": UseAbility(),
    "c": UiAction.SHEET, ">": UiAction.DESCEND, "enter": UiAction.DESCEND, "f5": UiAction.SKIP,
}  # fmt: skip
for _d, _keys in _STEP_KEYS.items():
    for _key in _keys:
        BINDINGS[_key] = Move(*_d)
    BINDINGS[_keys[-1].upper()] = Run(*_d)  # Shift + vi key
for _name, _d in _SHIFT_ARROWS.items():
    BINDINGS[f"shift+{_name}"] = Run(*_d)


def lookup(key: str, character: str | None) -> Command | UiAction | None:
    """Look up by Textual key name first, then by the typed character ('.' arrives as full_stop)."""
    if key in BINDINGS:
        return BINDINGS[key]
    return BINDINGS.get(character) if character else None
