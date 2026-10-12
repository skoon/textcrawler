"""Company memo templates (data/text/memos.toml)."""

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources
from string import Formatter


class MemoError(ValueError):
    pass


@dataclass(frozen=True)
class MemoBook:
    senders: tuple[str, ...]
    subjects: tuple[str, ...]
    openers: tuple[str, ...]
    policies: tuple[tuple[str, str], ...]  # contradicting pairs
    reminders: tuple[str, ...]
    signoffs: tuple[str, ...]
    graveyard_notice: str  # {level} {premium}
    plain_notice: str  # {level}


def _strings(raw: dict[str, object], name: str) -> tuple[str, ...]:
    entries = raw.get(name)
    if not isinstance(entries, list) or not entries:
        raise MemoError(f"{name} must be a non-empty list of strings")
    if not all(isinstance(e, str) and e for e in entries):
        raise MemoError(f"{name} must hold non-empty strings")
    return tuple(entries)


def _notice(raw: dict[str, object], name: str, fields: set[str]) -> str:
    notice = raw.get(name)
    if not isinstance(notice, str):
        raise MemoError(f"{name} must be a string")
    used = {f for _, f, _, _ in Formatter().parse(notice) if f}
    if used != fields:
        raise MemoError(f"{name} must use exactly the fields {sorted(fields)}, uses {sorted(used)}")
    return notice


def parse_memos(text: str) -> MemoBook:
    raw = tomllib.loads(text)
    known = {"senders", "subjects", "openers", "policies", "reminders", "signoffs",
             "graveyard_notice", "plain_notice"}  # fmt: skip
    if set(raw) != known:
        raise MemoError(f"memos.toml needs exactly {sorted(known)}, got {sorted(raw)}")
    pairs = raw["policies"]
    if not isinstance(pairs, list) or not pairs:
        raise MemoError("policies must be a list of pairs")
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]:
            raise MemoError(f"each policy must be a pair of two different lines, got {pair!r}")
        if not all(isinstance(line, str) and line for line in pair):
            raise MemoError(f"each policy pair must be two non-empty strings, got {pair!r}")
    return MemoBook(
        _strings(raw, "senders"),
        _strings(raw, "subjects"),
        _strings(raw, "openers"),
        tuple((p[0], p[1]) for p in pairs),
        _strings(raw, "reminders"),
        _strings(raw, "signoffs"),
        _notice(raw, "graveyard_notice", {"level", "premium"}),
        _notice(raw, "plain_notice", {"level"}),
    )


@cache
def load_memos() -> MemoBook:
    text = resources.files("minetoofar").joinpath("data", "text", "memos.toml").read_text("utf-8")
    return parse_memos(text)
