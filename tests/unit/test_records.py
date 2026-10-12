"""The personnel file (GDD 11): one record for every run that ends, kept in records.json."""

import json
from pathlib import Path

import pytest

from minetoofar.core.seed import Seed
from minetoofar.persist.errors import SaveError
from minetoofar.persist.records import (
    RECORDS_FILE,
    Record,
    append_record,
    make_record,
    read_records,
)
from minetoofar.sim.game import Game
from tests.helpers import BALANCE

SEED = Seed.parse("GOLD0012")


def dead_game() -> Game:
    g = Game.new(SEED, 3, rank=3)
    g.player.ready_at = 4200
    g.dead, g.cause = True, "Shambling Miner"
    g.check_out()
    return g


def test_a_death_makes_a_record_of_who_where_and_how_it_went() -> None:
    g = dead_game()
    r = make_record(g, "death")
    assert (r.seed, r.class_id, r.outcome, r.level, r.cleared) == (
        "1:GOLD0012",
        "fighter",
        "death",
        3,
        0,
    )
    assert (r.cause, r.turns, r.rank) == ("Shambling Miner", 42, 3)
    assert r.score == g.score() and r.title == "terminated"


def test_a_victory_has_no_cause_and_a_title_earned() -> None:
    g = Game.new(SEED, 5, rank=5)
    g.account = g.account.__class__(wallet=120)
    g.check_out()
    r = make_record(g, "victory")
    assert r.outcome == "victory" and r.cause == "" and r.cleared == 1
    assert r.score == 120 + BALANCE.economy.base_fee + 10 and r.title == "employee"


def test_only_deaths_and_victories_are_records() -> None:
    with pytest.raises(ValueError, match="outcome"):
        make_record(dead_game(), "retired")


def test_records_are_appended_in_order(tmp_path: Path) -> None:
    assert read_records(tmp_path) == []
    first, second = make_record(dead_game(), "death"), make_record(dead_game(), "death")
    append_record(tmp_path, first)
    append_record(tmp_path, Record(**{**second.__dict__, "score": 7}))
    got = read_records(tmp_path)
    assert [r.score for r in got] == [first.score, 7]
    assert [p.name for p in tmp_path.iterdir()] == [RECORDS_FILE]


def test_the_file_is_readable_json_with_a_version(tmp_path: Path) -> None:
    append_record(tmp_path, make_record(dead_game(), "death"))
    data = json.loads((tmp_path / RECORDS_FILE).read_text())
    assert data["records_version"] == 1 and data["records"][0]["seed"] == "1:GOLD0012"


@pytest.mark.parametrize(
    "text",
    ["", "not json", "\x00" * 40, "[]", '{"records_version": 2, "records": []}',
     '{"records_version": 1, "records": [{"seed": "x"}]}', '{"records_version": 1}'],
)  # fmt: skip
def test_a_damaged_file_is_reported_and_never_overwritten(tmp_path: Path, text: str) -> None:
    (tmp_path / RECORDS_FILE).write_text(text)
    with pytest.raises(SaveError, match="personnel file"):
        read_records(tmp_path)
    with pytest.raises(SaveError, match="personnel file"):
        append_record(tmp_path, make_record(dead_game(), "death"))
    assert (tmp_path / RECORDS_FILE).read_text() == text  # kept for you to look at
