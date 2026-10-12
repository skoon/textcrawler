"""The employment history screen's text (GDD 11): one entry per ended run, newest first."""

from minetoofar.content.balance import LEVELS
from minetoofar.content.text import load_text
from minetoofar.persist.records import Record
from minetoofar.ui.personnel import SHOWN, record_lines

TEXT = load_text()


def rec(
    n: int = 1, outcome: str = "victory", score: int = 90, title: str = "senior", cause: str = ""
) -> Record:
    level = LEVELS if outcome == "victory" else 3
    return Record(f"1:SEED{n:04d}", "fighter", outcome, 2, level, level, score, title, cause, 500)


def lines(records: list[Record]) -> list[str]:
    return record_lines(records, TEXT)


def test_an_empty_file_says_so() -> None:
    out = lines([])
    assert out[0] == TEXT.line("records_title")
    assert TEXT.line("records_none") in out


def test_a_victory_shows_class_score_title_and_the_seed() -> None:
    text = "\n".join(lines([rec(7, "victory", 92, "senior")]))
    assert "Fighter" in text and "92" in text and TEXT.line("title_senior") in text
    assert "1:SEED0007" in text
    assert TEXT.line("records_victory", cleared=LEVELS) in text


def test_a_death_shows_where_and_what_did_it() -> None:
    text = "\n".join(lines([rec(2, "death", -12, "terminated", "Foreman Grimsby")]))
    assert TEXT.line("title_terminated") in text and "-12" in text
    assert "Foreman Grimsby" in text and f"Work Order 3 of {LEVELS}" in text


def test_the_newest_run_is_listed_first() -> None:
    text = "\n".join(lines([rec(1), rec(2), rec(3)]))
    assert text.index("SEED0003") < text.index("SEED0002") < text.index("SEED0001")


def test_a_long_history_shows_the_latest_and_counts_the_rest() -> None:
    out = lines([rec(n) for n in range(1, SHOWN + 6)])
    text = "\n".join(out)
    assert f"SEED{SHOWN + 5:04d}" in text and "SEED0001" not in text
    assert TEXT.line("records_more", count=5) in out


def test_every_line_fits_an_80_column_terminal_with_room_for_the_frame() -> None:
    worst = rec(9999, "death", -123, "terminated", "Prospector Vane the Unlicensed Surveyor")
    assert all(len(line) <= 68 for line in lines([worst] * SHOWN))


def test_the_screen_ends_by_saying_how_to_leave() -> None:
    assert lines([rec()])[-1] == TEXT.line("records_back")
