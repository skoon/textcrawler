"""The personnel file (GDD 11): `records.json` gets one entry for every run that ends."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from minetoofar.core.seed import Seed
from minetoofar.persist.errors import SaveError
from minetoofar.persist.save import write_atomic
from minetoofar.sim.economy import title_key
from minetoofar.sim.game import Game

RECORDS_FILE = "records.json"
RECORDS_VERSION = 1
OUTCOMES = ("death", "victory")


@dataclass(frozen=True)
class Record:
    seed: str  # the share code
    class_id: str
    outcome: str  # death | victory
    rank: int
    level: int  # the level it ended on
    cleared: int  # levels finished
    score: int
    title: str  # the final title's key
    cause: str  # of death; empty for a victory
    turns: int


def make_record(game: Game, outcome: str) -> Record:
    """The entry for a run that has just ended, after its last slip was signed."""
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")
    score = game.score()
    return Record(
        Seed(game.spec.seed).share_code, game.player.class_id, outcome, game.player.rank,
        game.spec.level, game.cleared, score, title_key(score, game.economy),
        game.cause if outcome == "death" else "", game.total_turns,
    )  # fmt: skip


def _damaged(why: str) -> SaveError:
    return SaveError(
        f"The personnel file ({RECORDS_FILE}) is damaged ({why}). It was left as it is; "
        "move it aside to start a new one."
    )


def read_records(folder: Path) -> list[Record]:
    path = folder / RECORDS_FILE
    if not path.is_file():
        return []
    try:
        data: Any = json.loads(path.read_bytes().decode("utf-8"))
        if data["records_version"] != RECORDS_VERSION:
            raise _damaged(f"its version is {data['records_version']!r}")
        return [Record(**row) for row in data["records"]]
    except SaveError:
        raise
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as err:
        raise _damaged("it cannot be read") from err


def append_record(folder: Path, record: Record) -> None:
    records = [*read_records(folder), record]
    text = json.dumps(
        {"records_version": RECORDS_VERSION, "records": [asdict(r) for r in records]}, indent=1
    )
    write_atomic(folder, RECORDS_FILE, text + "\n")
