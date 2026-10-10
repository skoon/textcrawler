"""Recorded input logs with a state-hash checkpoint after every command (plan 5.6).

A log is evidence, not a save: it replays a session from its start and is never migrated.
"""

import json
from dataclasses import dataclass

from minetoofar.core.seed import Seed
from minetoofar.sim.events import (
    Command,
    Disarm,
    Event,
    Move,
    Run,
    SetRank,
    ToggleTorch,
    UseAbility,
    Wait,
)
from minetoofar.sim.game import Game


class ReplayError(ValueError):
    pass


class ReplayMismatch(ReplayError):
    def __init__(self, index: int, expected: str, actual: str) -> None:
        super().__init__(f"state diverged after command {index}: expected {expected}, got {actual}")
        self.index = index


@dataclass
class Recording:
    seed: str
    level: int
    class_id: str
    rank: int
    commands: list[Command]
    hashes: list[str]  # hashes[i] is Game.state_hash() after commands[i]


def encode_command(command: Command) -> str:
    match command:
        case Move(dx, dy):
            return f"m {dx} {dy}"
        case Run(dx, dy):
            return f"r {dx} {dy}"
        case Wait():
            return "w"
        case ToggleTorch():
            return "t"
        case SetRank(rank):
            return f"k {rank}"
        case UseAbility():
            return "a"
        case Disarm(dx, dy):
            return f"d {dx} {dy}"


def decode_command(text: str) -> Command:
    parts = text.split()
    try:
        match parts:
            case ["m", dx, dy]:
                return Move(int(dx), int(dy))
            case ["r", dx, dy]:
                return Run(int(dx), int(dy))
            case ["w"]:
                return Wait()
            case ["t"]:
                return ToggleTorch()
            case ["k", rank]:
                return SetRank(int(rank))
            case ["a"]:
                return UseAbility()
            case ["d", dx, dy]:
                return Disarm(int(dx), int(dy))
    except ValueError:
        pass
    raise ReplayError(f"bad command {text!r}")


def dumps(rec: Recording) -> str:
    """One field per line so a committed log diffs readably."""
    lines = [
        "{",
        f' "seed": {json.dumps(rec.seed)},',
        f' "level": {rec.level},',
        f' "class": {json.dumps(rec.class_id)},',
        f' "rank": {rec.rank},',
        f' "commands": {json.dumps([encode_command(c) for c in rec.commands])},',
        ' "hashes": [',
        ",\n".join(f"  {json.dumps(h)}" for h in rec.hashes),
        " ]",
        "}",
    ]
    return "\n".join(lines) + "\n"


def loads(text: str) -> Recording:
    try:
        raw = json.loads(text)
        return Recording(
            raw["seed"],
            raw["level"],
            raw["class"],
            raw["rank"],
            [decode_command(c) for c in raw["commands"]],
            list(raw["hashes"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as err:
        raise ReplayError(f"unreadable replay log: {err!r}") from err


class Recorder:
    """Wraps a Game so every command sent through `submit` is logged with its checkpoint."""

    def __init__(self, game: Game, seed: str, level: int, class_id: str, rank: int) -> None:
        self.game = game
        self.recording = Recording(seed, level, class_id, rank, [], [])

    def submit(self, command: Command) -> list[Event]:
        events = self.game.submit(command)  # a refused command (GameOver) is never logged
        self.recording.commands.append(command)
        self.recording.hashes.append(self.game.state_hash())
        return events


def replay(rec: Recording) -> Game:
    """Re-run a log from its start; raises ReplayMismatch at the first diverging checkpoint."""
    if not rec.hashes or len(rec.hashes) != len(rec.commands):
        raise ReplayError("a log needs one checkpoint per command; this one proves nothing")
    game = Game.new(Seed.parse(rec.seed), rec.level, rec.rank, rec.class_id)
    for i, (command, expected) in enumerate(zip(rec.commands, rec.hashes, strict=True)):
        game.submit(command)
        actual = game.state_hash()
        if actual != expected:
            raise ReplayMismatch(i, expected, actual)
    return game
