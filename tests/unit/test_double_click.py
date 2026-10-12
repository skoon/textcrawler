"""Double-clicking the EXE opens a console that closes the moment the game stops, so a refusal
(an unwritable save folder, say) would vanish unread. On a failure the window waits for Enter."""

import pytest

from minetoofar.__main__ import hold_window, owns_console


@pytest.mark.parametrize(
    ("processes", "one_file", "alone"),
    [(1, False, True), (2, False, False), (2, True, True), (3, True, False), (1, True, True)],
)
def test_a_console_shared_with_a_shell_is_not_ours(
    processes: int, one_file: bool, alone: bool
) -> None:
    # a one-file EXE is two processes (the bootstrap and the game); a shell makes it one more
    assert owns_console(processes, one_file) is alone


def test_a_failure_in_our_own_window_waits_for_enter(
    capsys: pytest.CaptureFixture[str],
) -> None:
    asked: list[str] = []
    hold_window(2, own_window=True, wait=lambda prompt: asked.append(prompt) or "")
    assert asked and "Enter" in asked[0]


def test_success_never_waits() -> None:
    hold_window(0, own_window=True, wait=lambda prompt: pytest.fail("waited after success"))


def test_a_shell_is_left_alone() -> None:
    hold_window(2, own_window=False, wait=lambda prompt: pytest.fail("waited in a shell"))


def test_a_closed_stdin_does_not_hang_or_crash() -> None:
    def closed(prompt: str) -> str:
        raise EOFError

    hold_window(2, own_window=True, wait=closed)
