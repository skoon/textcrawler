"""A recorded input log must replay to the same state at every checkpoint (GDD 10.7, plan 5.6)."""

from dataclasses import replace
from pathlib import Path

import pytest

from minetoofar.core.seed import Seed
from minetoofar.sim.bot import play
from minetoofar.sim.events import (
    DropItem,
    Equip,
    Move,
    Pickup,
    Run,
    SetRank,
    ToggleTorch,
    UseItem,
    Wait,
)
from minetoofar.sim.game import Game
from minetoofar.sim.replay import (
    Recorder,
    Recording,
    ReplayError,
    ReplayMismatch,
    dumps,
    loads,
    replay,
)

REPLAYS = Path(__file__).parent / "replay"


def record(seed: str, level: int, rank: int = 1, limit: int = 300) -> tuple[Game, Recording]:
    game = Game.new(Seed.parse(seed), level, rank)
    recorder = Recorder(game, seed, level, "fighter", rank)
    play(game, recorder.submit, limit)
    return game, recorder.recording


def test_a_played_game_replays_to_the_same_state_at_every_checkpoint() -> None:
    game, recording = record("GOLD0001", 2)
    assert len(recording.commands) == len(recording.hashes) > 20
    again = replay(recording)
    assert again.state_hash() == game.state_hash() == recording.hashes[-1]


@pytest.mark.parametrize(("seed", "level"), [("BRASSLAMP42", 1), ("GOLD0007", 5), ("GOLD0042", 3)])
def test_replay_works_across_seeds_and_levels(seed: str, level: int) -> None:
    game, recording = record(seed, level)
    assert replay(recording).state_hash() == game.state_hash()


def test_different_seeds_end_in_different_states() -> None:
    assert record("GOLD0001", 1)[0].state_hash() != record("GOLD0002", 1)[0].state_hash()


def test_the_text_form_round_trips() -> None:
    _, recording = record("GOLD0001", 1, limit=60)
    assert loads(dumps(recording)) == recording


def test_every_command_kind_survives_the_text_form() -> None:
    rec = Recording(
        "A",
        1,
        "fighter",
        2,
        [
            Move(1, -1),
            Run(-1, 0),
            Wait(),
            ToggleTorch(),
            SetRank(3),
            Pickup(),
            Equip(2, True),
            Equip(0),
            UseItem(1),
            DropItem(3),
        ],  # fmt: skip
        ["h"] * 11,
    )
    assert loads(dumps(rec)) == rec


def test_a_changed_command_is_caught_at_the_step_where_the_game_diverges() -> None:
    _, recording = record("GOLD0001", 2, limit=80)
    tampered = replace(recording, commands=[*recording.commands])
    tampered.commands[10] = Wait()
    with pytest.raises(ReplayMismatch) as err:
        replay(tampered)
    assert 10 <= err.value.index < 80


def test_a_changed_checkpoint_hash_is_caught() -> None:
    _, recording = record("GOLD0001", 1, limit=30)
    bad = replace(recording, hashes=[*recording.hashes])
    bad.hashes[7] = "0" * 64
    with pytest.raises(ReplayMismatch) as err:
        replay(bad)
    assert err.value.index == 7


def test_a_log_without_checkpoints_proves_nothing_and_is_refused() -> None:
    rec = Recording("GOLD0001", 1, "fighter", 1, [Wait()], [])
    with pytest.raises(ReplayError, match="checkpoint"):
        replay(rec)
    with pytest.raises(ReplayError, match="checkpoint"):
        replay(Recording("GOLD0001", 1, "fighter", 1, [], []))


def test_commands_and_hashes_must_pair_up() -> None:
    with pytest.raises(ReplayError, match="checkpoint"):
        replay(Recording("GOLD0001", 1, "fighter", 1, [Wait(), Wait()], ["a"]))


def test_malformed_text_fails_loudly() -> None:
    with pytest.raises(ReplayError):
        loads("not json")
    with pytest.raises(ReplayError, match="command"):
        loads(
            '{"seed": "A", "level": 1, "class": "fighter", "rank": 1,'
            ' "commands": ["z 1"], "hashes": ["x"]}'
        )


def test_a_rank_command_replays_too() -> None:
    game = Game.new(Seed.parse("GOLD0003"), 1)
    recorder = Recorder(game, "GOLD0003", 1, "fighter", 1)
    recorder.submit(SetRank(4))
    recorder.submit(Wait())
    assert replay(recorder.recording).player.rank == 4


@pytest.mark.parametrize("path", sorted(REPLAYS.glob("*.json")), ids=lambda p: p.name)
def test_committed_logs_still_replay_exactly(path: Path) -> None:
    recording = loads(path.read_text("utf-8"))
    assert len(recording.hashes) > 20
    replay(recording)  # raises ReplayMismatch if any rule, number, or RNG draw drifted


def test_there_is_at_least_one_committed_log() -> None:
    assert list(REPLAYS.glob("*.json"))
