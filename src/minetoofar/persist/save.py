"""The one save slot (GDD 11): `run.json`, human-readable and versioned, written atomically.

The terrain and the monsters are not in it: they are regenerated from the seed, and a hash of the
regenerated level is stored so a save made with a different generator stops with a clear message
instead of loading a different mine. Nothing here falls back to a guess."""

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from minetoofar.content.balance import LEVELS
from minetoofar.content.gamedata import RANKS, load_gamedata
from minetoofar.core.seed import GEN_VERSION, Seed, SeedError
from minetoofar.gen.world import STAGES, generate_world
from minetoofar.persist.errors import SaveError
from minetoofar.sim.game import Carry, Game
from minetoofar.sim.snapshot import (
    SnapshotError,
    carry_from_dict,
    carry_to_dict,
    game_from_dict,
    game_to_dict,
)

SAVE_VERSION = 1
SAVE_FILE = "run.json"
MARKER = "A Mine Too Far"
LOG_KEPT = 30

# Forward migrations: MIGRATIONS[n] turns a version-n save into a version-(n+1) one. None yet:
# version 1 is the first.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


@dataclass
class SavedRun:
    """A run as it stood when it was saved: in the middle of `level` (`game`), or at the Shaft
    about to arrive on it (`game` is None and `arrival` is what comes down)."""

    seed: str
    class_id: str
    start_rank: int
    level: int
    arrival: Carry | None
    game: Game | None
    log: list[str] = field(default_factory=list)


def world_sha(seed: Seed, level: int) -> str:
    """One hash for the whole generated level: every stage's, so any change to the mine shows."""
    world = generate_world(seed, level)
    return hashlib.sha256(
        "".join(world.stage(s).sha256 for s in STAGES).encode("ascii")
    ).hexdigest()


def to_json(run: SavedRun) -> str:
    data = {
        "game": MARKER,
        "save_version": SAVE_VERSION,
        "gen_version": GEN_VERSION,
        "seed": run.seed,
        "class_id": run.class_id,
        "start_rank": run.start_rank,
        "level": run.level,
        "layout_sha": world_sha(Seed(run.seed), run.level),
        "arrival": None if run.arrival is None else carry_to_dict(run.arrival),
        "state": None if run.game is None else game_to_dict(run.game),
        "log": run.log[-LOG_KEPT:],
    }
    return json.dumps(data, indent=1) + "\n"


def _damaged(why: str) -> SaveError:
    return SaveError(f"The save file is damaged ({why}). It was not loaded.")


def _migrated(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("save_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise _damaged("it has no usable version number")
    if version > SAVE_VERSION:
        raise SaveError(
            f"This save was made by a newer version of the game (save format {version}; "
            f"this game reads up to {SAVE_VERSION}). It was not loaded."
        )
    while version < SAVE_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:
            raise SaveError(
                f"This save is from an old version (format {version}) and cannot be brought up "
                "to date. It was not loaded."
            )
        data = step(data)
        version += 1
        data["save_version"] = version
    return data


def from_json(text: str) -> SavedRun:
    """Parse and check a save; every way it can be wrong ends in a SaveError saying so."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as err:
        raise _damaged("it is not valid JSON") from err
    if not isinstance(data, dict) or data.get("game") != MARKER:
        raise SaveError("This file is not a Mine Too Far save. It was not loaded.")
    data = _migrated(data)
    try:
        return _build(data)
    except SnapshotError as err:
        raise _damaged(str(err)) from err
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, SeedError) as err:
        raise _damaged(f"something in it is missing or wrong: {err!r}") from err


def _build(data: dict[str, Any]) -> SavedRun:
    if data["gen_version"] != GEN_VERSION:
        raise SaveError(
            f"This save was made with a different mine generator (version {data['gen_version']}; "
            f"this game uses {GEN_VERSION}). It was not loaded."
        )
    seed = Seed.parse(data["seed"])
    level, rank, class_id = data["level"], data["start_rank"], data["class_id"]
    if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= LEVELS:
        raise ValueError(f"level {level!r}")
    if not isinstance(rank, int) or isinstance(rank, bool) or not 1 <= rank <= RANKS:
        raise ValueError(f"rank {rank!r}")
    if class_id not in load_gamedata().classes:
        raise ValueError(f"class {class_id!r}")
    log = data["log"]
    if not isinstance(log, list) or not all(isinstance(line, str) for line in log):
        raise ValueError("the log is not a list of lines")
    if data["layout_sha"] != world_sha(seed, level):
        raise SaveError(
            "This save was made with a different mine. The generator has changed since it was "
            "written, so it cannot be loaded."
        )
    arrival = None if data["arrival"] is None else carry_from_dict(data["arrival"])
    game = None if data["state"] is None else game_from_dict(data["state"])
    if game is None and arrival is None:
        raise SnapshotError("it holds neither a level in play nor a way into one")
    if game is not None and (game.spec.seed != seed.canonical or game.spec.level != level):
        raise SnapshotError("the level in play is not the one the header names")
    return SavedRun(seed.canonical, class_id, rank, level, arrival, game, list(log))


# -- the disk --------------------------------------------------------------------------


def has_save(folder: Path) -> bool:
    return (folder / SAVE_FILE).is_file()


def write_atomic(folder: Path, name: str, text: str) -> None:
    """Write `name.tmp`, flush it to the disk, then swap it in: a crash leaves the old file."""
    target, temp = folder / name, folder / (name + ".tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    except OSError as err:
        raise SaveError(f"could not save to {folder}: {err.strerror or err}") from err


def write_save(folder: Path, run: SavedRun) -> None:
    write_atomic(folder, SAVE_FILE, to_json(run))


def load_save(folder: Path) -> SavedRun:
    path = folder / SAVE_FILE
    if not path.is_file():
        raise SaveError("There is no saved run.")
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as err:
        raise _damaged(f"it cannot be read: {err}") from err
    return from_json(text)


def delete_save(folder: Path) -> None:
    try:
        (folder / SAVE_FILE).unlink(missing_ok=True)
    except OSError as err:
        raise SaveError(
            f"could not remove the old save in {folder}: {err.strerror or err}"
        ) from err
