"""The save file (GDD 11): versioned JSON, atomic, and it refuses what it cannot trust."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from minetoofar.core.seed import GEN_VERSION, Seed
from minetoofar.persist import save as save_module
from minetoofar.persist.errors import SaveError
from minetoofar.persist.save import (
    SAVE_FILE,
    SavedRun,
    delete_save,
    from_json,
    has_save,
    load_save,
    to_json,
    write_save,
)
from minetoofar.sim.bot import play
from minetoofar.sim.game import Game

SEED = "GOLD0012"


def mid_level_run() -> SavedRun:
    g = Game.new(Seed.parse(SEED), 2, rank=3)
    play(g, g.submit, 60)
    return SavedRun(SEED, "fighter", 1, 2, None, g, ["Welcome.", "You hit the Miner."])


def check_in_run() -> SavedRun:
    g = Game.new(Seed.parse(SEED), 1)
    g.check_out()
    return SavedRun(SEED, "fighter", 1, 2, g.carry_over(), None, [])


def raw(run: SavedRun) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(to_json(run))
    return out


def expect(text: str, *words: str) -> None:
    with pytest.raises(SaveError) as err:
        from_json(text)
    for word in words:
        assert word in str(err.value), (word, str(err.value))


# -- what is written -------------------------------------------------------------------


def test_a_level_in_play_round_trips_through_text() -> None:
    run = mid_level_run()
    back = from_json(to_json(run))
    assert back.game is not None and run.game is not None
    assert back.game.state_hash() == run.game.state_hash()
    assert (back.seed, back.class_id, back.start_rank, back.level) == (SEED, "fighter", 1, 2)
    assert back.log == run.log and back.arrival is None


def test_a_check_in_save_has_no_game_only_the_arrival() -> None:
    run = check_in_run()
    back = from_json(to_json(run))
    assert back.game is None and back.arrival == run.arrival and back.level == 2


def test_the_file_carries_its_markers() -> None:
    data = raw(mid_level_run())
    assert data["game"] == "A Mine Too Far" and data["save_version"] == save_module.SAVE_VERSION
    assert data["gen_version"] == GEN_VERSION and data["seed"] == SEED
    assert len(data["layout_sha"]) == 64


def test_a_save_is_stable_text() -> None:
    run = mid_level_run()
    assert to_json(run) == to_json(run) and to_json(run).endswith("\n")
    assert to_json(run).isascii()


# -- the disk --------------------------------------------------------------------------


def test_writing_then_loading_a_folder(tmp_path: Path) -> None:
    assert not has_save(tmp_path)
    run = mid_level_run()
    write_save(tmp_path, run)
    assert has_save(tmp_path) and [p.name for p in tmp_path.iterdir()] == [SAVE_FILE]
    loaded = load_save(tmp_path)
    assert loaded.game is not None and run.game is not None
    assert loaded.game.state_hash() == run.game.state_hash()
    assert has_save(tmp_path)  # loading does not delete it


def test_a_second_save_replaces_the_first(tmp_path: Path) -> None:
    write_save(tmp_path, check_in_run())
    write_save(tmp_path, mid_level_run())
    assert load_save(tmp_path).game is not None


def test_an_interrupted_write_leaves_the_previous_save_loadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = check_in_run()
    write_save(tmp_path, first)
    before = (tmp_path / SAVE_FILE).read_bytes()

    def yanked(src: Any, dst: Any) -> None:
        raise OSError("the power went out")

    monkeypatch.setattr(os, "replace", yanked)
    with pytest.raises(SaveError, match="could not save"):
        write_save(tmp_path, mid_level_run())
    monkeypatch.undo()
    assert (tmp_path / SAVE_FILE).read_bytes() == before
    assert load_save(tmp_path).arrival == first.arrival
    write_save(tmp_path, mid_level_run())  # and a later save works, stale temp file or not
    assert load_save(tmp_path).game is not None


def test_a_temp_file_alone_is_not_a_saved_run(tmp_path: Path) -> None:
    (tmp_path / (SAVE_FILE + ".tmp")).write_text(to_json(mid_level_run()))
    assert not has_save(tmp_path)
    with pytest.raises(SaveError, match="no saved run"):
        load_save(tmp_path)


def test_deleting_removes_the_save_and_is_fine_when_there_is_none(tmp_path: Path) -> None:
    write_save(tmp_path, check_in_run())
    delete_save(tmp_path)
    assert not has_save(tmp_path)
    delete_save(tmp_path)


def test_a_unwritable_folder_is_a_clear_error(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(SaveError, match="could not save"):
        write_save(blocker / "inside", check_in_run())


# -- what it will not load -------------------------------------------------------------


def test_text_that_is_not_json_is_a_damaged_save() -> None:
    expect("this is not json", "damaged")
    expect("", "damaged")
    expect("\x00" * 500, "damaged")


def test_a_truncated_file_is_a_damaged_save() -> None:
    text = to_json(mid_level_run())
    expect(text[: len(text) // 2], "damaged")


def test_json_from_another_program_is_not_ours() -> None:
    expect('{"hello": "world"}', "not a Mine Too Far save")
    expect("[1, 2, 3]", "not a Mine Too Far save")
    expect('{"game": "Another Game", "save_version": 1}', "not a Mine Too Far save")


def test_a_newer_save_is_refused_with_both_versions_named() -> None:
    data = raw(check_in_run())
    data["save_version"] = save_module.SAVE_VERSION + 1
    expect(json.dumps(data), "newer version", str(save_module.SAVE_VERSION + 1))


def test_a_save_without_a_version_is_damaged() -> None:
    data = raw(check_in_run())
    del data["save_version"]
    expect(json.dumps(data), "damaged")
    data["save_version"] = "one"
    expect(json.dumps(data), "damaged")


def test_an_older_save_is_migrated_step_by_step(monkeypatch: pytest.MonkeyPatch) -> None:
    data = raw(check_in_run())
    data["old_name"] = data.pop("log")  # what version 1 called it, pretend

    def one_to_two(d: dict[str, Any]) -> dict[str, Any]:
        d["log"] = d.pop("old_name")
        return d

    monkeypatch.setattr(save_module, "SAVE_VERSION", 2)
    monkeypatch.setattr(save_module, "MIGRATIONS", {1: one_to_two})
    data["save_version"] = 1
    run = from_json(json.dumps(data))
    assert run.log == [] and run.level == 2


def test_a_missing_migration_is_an_error_not_a_guess(monkeypatch: pytest.MonkeyPatch) -> None:
    data = raw(check_in_run())
    monkeypatch.setattr(save_module, "SAVE_VERSION", 3)
    monkeypatch.setattr(save_module, "MIGRATIONS", {})
    expect(json.dumps(data), "cannot be brought up to date")


def test_a_save_from_another_generator_is_refused() -> None:
    data = raw(check_in_run())
    data["gen_version"] = GEN_VERSION + 1
    expect(json.dumps(data), "different mine generator")


def test_a_save_whose_mine_no_longer_matches_is_refused() -> None:
    data = raw(check_in_run())
    data["layout_sha"] = "0" * 64
    expect(json.dumps(data), "different mine")
    data = raw(check_in_run())
    data["seed"] = "GOLD0013"  # same level number, another seed: another mine
    expect(json.dumps(data), "different mine")


@pytest.mark.parametrize(
    "damage",
    [
        lambda d: d.__setitem__("level", 9),
        lambda d: d.__setitem__("level", "two"),
        lambda d: d.__setitem__("class_id", "wizard"),
        lambda d: d.__setitem__("seed", "not a seed!"),
        lambda d: d.__setitem__("start_rank", 0),
        lambda d: d.__setitem__("log", "text"),
        lambda d: d.pop("arrival"),
        lambda d: d.__setitem__("state", {"seed": SEED}),
    ],
)
def test_nonsense_fields_are_a_save_error_not_a_crash(damage: Any) -> None:
    data = raw(check_in_run())
    damage(data)
    with pytest.raises(SaveError):
        from_json(json.dumps(data))


def test_a_state_that_disagrees_with_the_header_is_refused() -> None:
    data = raw(mid_level_run())
    data["level"] = 3
    data["layout_sha"] = save_module.world_sha(Seed.parse(SEED), 3)
    expect(json.dumps(data), "damaged")


def test_a_save_with_neither_a_game_nor_an_arrival_is_damaged() -> None:
    data = raw(check_in_run())
    data["arrival"] = None
    expect(json.dumps(data), "damaged")


def test_a_first_level_save_may_have_no_arrival_and_no_game() -> None:
    g = Game.new(Seed.parse(SEED), 1)
    run = SavedRun(SEED, "fighter", 1, 1, None, g, [])
    assert from_json(to_json(run)).game is not None
