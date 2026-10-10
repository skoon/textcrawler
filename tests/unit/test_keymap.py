import pytest

from minetoofar.sim.events import Move, Run, ToggleTorch, UseAbility, Wait
from minetoofar.ui.keymap import UiAction, lookup

# direction -> (arrow, vi, digit, run vi key)
COMPASS = {
    (0, -1): ("up", "k", "8", "K"),
    (1, -1): ("pageup", "u", "9", "U"),
    (1, 0): ("right", "l", "6", "L"),
    (1, 1): ("pagedown", "n", "3", "N"),
    (0, 1): ("down", "j", "2", "J"),
    (-1, 1): ("end", "b", "1", "B"),
    (-1, 0): ("left", "h", "4", "H"),
    (-1, -1): ("home", "y", "7", "Y"),
}


@pytest.mark.parametrize(("d", "keys"), COMPASS.items())
def test_every_direction_has_arrow_vi_and_numpad_keys(
    d: tuple[int, int], keys: tuple[str, str, str, str]
) -> None:
    arrow, vi, digit, run = keys
    for key in (arrow, vi, digit):
        assert lookup(key, None) == Move(*d)
    assert lookup(run, run) == Run(*d)


@pytest.mark.parametrize(
    ("key", "d"),
    [
        ("shift+up", (0, -1)),
        ("shift+down", (0, 1)),
        ("shift+left", (-1, 0)),
        ("shift+right", (1, 0)),
    ],
)
def test_shift_arrows_run(key: str, d: tuple[int, int]) -> None:
    assert lookup(key, None) == Run(*d)


@pytest.mark.parametrize(("key", "char"), [("5", "5"), ("space", " "), ("full_stop", ".")])
def test_wait_keys(key: str, char: str) -> None:
    assert lookup(key, char) == Wait()


def test_ui_actions() -> None:
    assert lookup("x", "x") is UiAction.LOOK
    assert lookup("Q", "Q") is UiAction.QUIT
    assert lookup("f2", None) is UiAction.GLYPHS
    assert lookup("ctrl+l", None) is UiAction.REDRAW
    assert lookup("t", "t") == ToggleTorch()


def test_lowercase_q_does_not_quit_and_unknown_keys_do_nothing() -> None:
    assert lookup("q", "q") is None
    assert lookup("z", "z") is None
    assert lookup("0", "0") is None


def test_the_ability_and_sheet_keys() -> None:
    assert lookup("a", "a") == UseAbility()
    assert lookup("c", "c") is UiAction.SHEET


def test_descend_and_the_debug_skip_keys() -> None:
    assert lookup("greater_than_sign", ">") is UiAction.DESCEND
    assert lookup("enter", None) is UiAction.DESCEND
    assert lookup("f5", None) is UiAction.SKIP
