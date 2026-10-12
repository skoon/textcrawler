"""Where the save lives (GDD 11, A28): next to the EXE when portable, else the OS data folder."""

import os
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from minetoofar.persist.errors import SaveError
from minetoofar.persist.paths import default_save_dir, ensure_writable, resolve_save_dir

HOME = PurePosixPath("/home/scott")


def test_the_portable_exe_keeps_everything_next_to_itself() -> None:
    exe = PureWindowsPath(r"D:\Games\MineTooFar\minetoofar.exe")
    got = default_save_dir("win32", {}, PureWindowsPath(r"C:\Users\skoon"), True, exe)
    assert got == PureWindowsPath(r"D:\Games\MineTooFar\MineTooFarData")


def test_a_source_run_on_windows_uses_appdata() -> None:
    env = {"APPDATA": r"C:\Users\skoon\AppData\Roaming"}
    got = default_save_dir("win32", env, PureWindowsPath(r"C:\Users\skoon"), False, None)
    assert got == PureWindowsPath(r"C:\Users\skoon\AppData\Roaming\MineTooFar")


def test_windows_without_appdata_asks_for_save_dir_instead_of_guessing() -> None:
    with pytest.raises(SaveError, match="APPDATA.*--save-dir"):
        default_save_dir("win32", {}, PureWindowsPath(r"C:\Users\skoon"), False, None)


def test_linux_follows_xdg_data_home_then_the_local_share_folder() -> None:
    assert default_save_dir(
        "linux", {"XDG_DATA_HOME": "/data"}, HOME, False, None
    ) == PurePosixPath("/data/minetoofar")
    assert default_save_dir("linux", {}, HOME, False, None) == PurePosixPath(
        "/home/scott/.local/share/minetoofar"
    )
    assert default_save_dir("linux", {"XDG_DATA_HOME": ""}, HOME, False, None) == PurePosixPath(
        "/home/scott/.local/share/minetoofar"
    )


def test_macos_uses_application_support() -> None:
    got = default_save_dir("darwin", {}, PurePosixPath("/Users/scott"), False, None)
    assert got == PurePosixPath("/Users/scott/Library/Application Support/MineTooFar")


def test_the_override_beats_every_default() -> None:
    got = resolve_save_dir(
        "/somewhere/else", platform="win32", env={}, home=HOME, frozen=True, exe=None
    )
    assert got == Path("/somewhere/else")


def test_resolving_without_an_override_uses_the_defaults() -> None:
    got = resolve_save_dir(None, platform="linux", env={}, home=HOME, frozen=False, exe=None)
    assert got == PurePosixPath("/home/scott/.local/share/minetoofar")


def test_a_missing_folder_is_created_and_returned(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "saves"
    assert ensure_writable(target) == target and target.is_dir()
    assert list(target.iterdir()) == []  # the write probe cleans up after itself


def test_a_file_where_the_folder_should_be_is_a_clear_error(tmp_path: Path) -> None:
    blocker = tmp_path / "saves"
    blocker.write_text("not a folder")
    with pytest.raises(SaveError, match="cannot use the save folder"):
        ensure_writable(blocker)


@pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="needs POSIX permissions and a non-root user",
)
def test_a_read_only_folder_is_a_clear_error_not_a_silent_fallback(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        with pytest.raises(SaveError, match="not writable"):
            ensure_writable(locked)
    finally:
        locked.chmod(0o700)


def test_an_unwritable_folder_reports_its_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def refuse(self: Path, *args: object, **kwargs: object) -> int:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "write_bytes", refuse)
    with pytest.raises(SaveError) as err:
        ensure_writable(tmp_path)
    assert str(tmp_path) in str(err.value) and "--save-dir" in str(err.value)


def test_a_frozen_exe_resolves_to_the_folder_beside_itself() -> None:
    exe = PureWindowsPath(r"E:\Portable\minetoofar.exe")
    got = resolve_save_dir(
        None, platform="win32", env={}, home=PureWindowsPath(r"C:\Users\x"), frozen=True, exe=exe
    )
    assert got == PureWindowsPath(r"E:\Portable\MineTooFarData")
