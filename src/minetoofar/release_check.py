"""What a built EXE can check about itself without a terminal (M10): play a whole run with the
scripted bot, and write or read a save. The EXE and the source must print identical lines, so
a release is proved the same game by comparing them."""

from pathlib import Path

from minetoofar.core.seed import Seed
from minetoofar.persist.save import SavedRun, load_save, world_sha, write_save
from minetoofar.sim.autoplay import play_run
from minetoofar.sim.bot import CAREFUL, Memory, choose
from minetoofar.sim.game import Game

SAVE_AFTER = 150  # commands played before the save is written: well inside Level 1


def autoplay_line(seed: Seed, class_id: str) -> str:
    """Play levels 1 to 5 with the careful bot and say how it went."""
    run = play_run(seed, class_id)
    return (
        f"autoplay ok: seed {seed.share_code} {class_id} {run.outcome} levels {len(run.levels)} "
        f"score {run.score} title {run.title} wallet {run.wallet} debt {run.debt}"
    )


def _describe(seed: Seed, class_id: str, game: Game) -> str:
    return (
        f"seed {seed.share_code} {class_id} level {game.spec.level} turn {game.total_turns} "
        f"layout {world_sha(seed, game.spec.level)[:16]} state {game.state_hash()[:16]}"
    )


def write_save_line(seed: Seed, class_id: str, folder: Path) -> str:
    """Play the first few turns of Level 1 and save the run in `folder`."""
    game = Game.new(seed, 1, 1, class_id)
    memory = Memory()
    for _ in range(SAVE_AFTER):
        if (command := choose(game, CAREFUL, memory)) is None:
            break
        game.submit(command)
    write_save(folder, SavedRun(seed.canonical, class_id, 1, 1, None, game, []))
    return f"save written: {_describe(seed, class_id, game)}"


def read_save_line(folder: Path) -> str:
    """Load the save in `folder` (every check the game makes) and describe what came back."""
    saved = load_save(folder)
    if saved.game is None:
        raise ValueError("this save is at a check-in, not in the middle of a level")
    return f"save ok: {_describe(Seed(saved.seed), saved.class_id, saved.game)}"
