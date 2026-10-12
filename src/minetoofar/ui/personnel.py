"""The employment history (GDD 11): the lines the title menu shows for the runs on file."""

from minetoofar.content.balance import LEVELS
from minetoofar.content.gamedata import load_gamedata
from minetoofar.content.text import Text
from minetoofar.persist.records import Record

SHOWN = 8  # entries on screen, newest first; two lines each
CAUSE_WIDTH = 24


def _entry(number: int, record: Record, text: Text) -> list[str]:
    classes = load_gamedata().classes
    head = text.line(
        "records_entry",
        number=number,
        class_name=classes[record.class_id].name,
        score=record.score,
        title=text.line(f"title_{record.title}"),
        seed=record.seed,
    )
    if record.outcome == "victory":
        return [head, text.line("records_victory", cleared=record.cleared)]
    cause = record.cause[:CAUSE_WIDTH]
    return [head, text.line("records_death", level=record.level, total=LEVELS, cause=cause)]


def record_lines(records: list[Record], text: Text) -> list[str]:
    """The screen's text: newest run first, the oldest left out once there are too many."""
    lines = [text.line("records_title"), ""]
    if not records:
        lines.append(text.line("records_none"))
    newest_first = list(reversed(records))
    for offset, record in enumerate(newest_first[:SHOWN]):
        lines += _entry(len(records) - offset, record, text)
    if len(records) > SHOWN:
        lines.append(text.line("records_more", count=len(records) - SHOWN))
    return [*lines, "", text.line("records_back")]
