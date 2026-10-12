"""Where the run lives on disk (GDD 11, A28). Everything is passed in, so tests can fake a
platform; `resolve_save_dir` with defaults is what the game calls."""

import os
import sys
from collections.abc import Mapping
from pathlib import Path, PurePath

from minetoofar.persist.errors import SaveError

APP_NAME = "MineTooFar"
PORTABLE_NAME = "MineTooFarData"


def default_save_dir(
    platform: str, env: Mapping[str, str], home: PurePath, frozen: bool, exe: PurePath | None
) -> PurePath:
    """The folder a run saves in when nobody said otherwise."""
    if frozen:
        if exe is None:
            raise SaveError("cannot find the program to put its data folder beside; use --save-dir")
        return exe.parent / PORTABLE_NAME
    if platform == "win32":
        appdata = env.get("APPDATA")
        if not appdata:
            raise SaveError("APPDATA is not set, so there is no place to save; use --save-dir")
        return type(home)(appdata) / APP_NAME
    if platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    data_home = env.get("XDG_DATA_HOME")
    base = type(home)(data_home) if data_home else home / ".local" / "share"
    return base / APP_NAME.lower()


def resolve_save_dir(
    override: str | None,
    platform: str = sys.platform,
    env: Mapping[str, str] | None = None,
    home: PurePath | None = None,
    frozen: bool | None = None,
    exe: PurePath | None = None,
) -> PurePath:
    """`--save-dir` first, then the portable folder, then the platform's own."""
    if override:
        return Path(override).expanduser()
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    where = Path(sys.executable) if exe is None and is_frozen else exe
    return default_save_dir(
        platform, os.environ if env is None else env, home or Path.home(), is_frozen, where
    )


def ensure_writable(folder: Path) -> Path:
    """Create the folder if need be and prove a file can be written there; never fall back."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        raise SaveError(f"cannot use the save folder {folder}: {err.strerror or err}") from err
    probe = folder / ".write-test"
    try:
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as err:
        raise SaveError(
            f"the save folder {folder} is not writable ({err.strerror or err}); "
            "choose another with --save-dir"
        ) from err
    return folder


def save_dir(override: str | None = None) -> Path:
    """The folder this run saves in, created and checked; raises SaveError if it cannot be used."""
    return ensure_writable(Path(resolve_save_dir(override)))
