"""The Rogue Humans' speech grammars (data/text/speech.toml), rendered once per level."""

import tomllib
from dataclasses import dataclass
from importlib import resources
from string import Formatter

from minetoofar.core.rng import Rng

MOODS = ("cheerful", "petty", "grandiose")
EVENTS = ("on_sight", "on_hit", "on_hurt", "on_flee", "on_death")  # the order lines are rolled in
REQUIRED = {
    "foreman_grimsby": ("on_sight", "on_hit", "on_hurt", "on_death"),  # he never retreats
    "prospector_vane": EVENTS,
}


class SpeechError(ValueError):
    pass


@dataclass(frozen=True)
class SpeechEvent:
    template: str
    slots: dict[str, dict[str, tuple[str, ...]]]  # slot -> mood -> options


@dataclass(frozen=True)
class SpeechBook:
    tics: dict[str, tuple[str, ...]]
    events: dict[str, dict[str, SpeechEvent]]


def _options(where: str, raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw or not all(isinstance(o, str) and o for o in raw):
        raise SpeechError(f"{where} must list options (non-empty strings)")
    return tuple(raw)


def _event(kind: str, name: str, raw: object) -> SpeechEvent:
    where = f"{kind}.{name}"
    if not isinstance(raw, dict) or not isinstance(raw.get("template"), str):
        raise SpeechError(f"{where} needs a template string")
    template: str = raw["template"]
    slots: dict[str, dict[str, tuple[str, ...]]] = {}
    for slot, moods in raw.items():
        if slot == "template":
            continue
        if not isinstance(moods, dict) or set(moods) != set(MOODS):
            missing = sorted(set(MOODS) - set(moods if isinstance(moods, dict) else ()))
            raise SpeechError(f"{where}.{slot} needs all moods; missing moods {missing}")
        slots[slot] = {mood: _options(f"{where}.{slot}.{mood}", moods[mood]) for mood in MOODS}
    for _, field, _, _ in Formatter().parse(template):
        if field is not None and field not in slots:
            raise SpeechError(f"{where} uses unknown slot {field!r}")
    return SpeechEvent(template, slots)


def parse_speech(text: str) -> SpeechBook:
    raw = tomllib.loads(text)
    if set(raw) != set(REQUIRED):
        raise SpeechError(f"speech.toml must define exactly {sorted(REQUIRED)}")
    tics: dict[str, tuple[str, ...]] = {}
    events: dict[str, dict[str, SpeechEvent]] = {}
    for kind, table in raw.items():
        tics[kind] = _options(f"{kind}.tics", table.get("tics"))
        named = {k: v for k, v in table.items() if k != "tics"}
        unknown = sorted(set(named) - set(EVENTS))
        if unknown:
            raise SpeechError(f"{kind} has unknown events {unknown}")
        missing = [e for e in REQUIRED[kind] if e not in named]
        if missing:
            raise SpeechError(f"{kind} is missing events {missing}")
        events[kind] = {name: _event(kind, name, named[name]) for name in EVENTS if name in named}
    return SpeechBook(tics, events)


def load_speech() -> SpeechBook:
    path = resources.files("minetoofar").joinpath("data", "text", "speech.toml")
    return parse_speech(path.read_text("utf-8"))


def render_lines(
    book: SpeechBook, kind: str, mood: str, tic_roll: int, rng: Rng, tic_one_in: int
) -> dict[str, str]:
    """Roll a human's lines: pick each slot's words for the mood, and tag the human's tic onto
    about one line in `tic_one_in`. A pure function of its inputs (the dice are `rng`)."""
    tic = book.tics[kind][tic_roll % len(book.tics[kind])]
    lines: dict[str, str] = {}
    for name, event in book.events[kind].items():
        words = {slot: rng.pick(moods[mood]) for slot, moods in event.slots.items()}
        text = event.template.format(**words)
        lines[name] = f"{text} {tic}" if rng.chance(1, tic_one_in) else text
    return lines
