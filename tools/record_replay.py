"""Record a scripted-bot session as a replay log (tests/scenario/replay/*.json). Usage:
    uv run python tools/record_replay.py GOLD0001 2 --out tests/scenario/replay/GOLD0001-L2.json
Optional: --class fighter|rogue|ranger, --rank N, --limit COMMANDS, and --first "k 3" --first t to
start with scripted commands.
Re-record only on purpose: a committed log is evidence that rules and dice did not drift.
"""

import argparse
from pathlib import Path

from minetoofar.core.seed import Seed
from minetoofar.sim.bot import play
from minetoofar.sim.game import Game
from minetoofar.sim.replay import Recorder, decode_command, dumps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed")
    parser.add_argument("level", type=int)
    parser.add_argument("--class", dest="class_id", default="fighter")
    parser.add_argument("--rank", type=int, default=1)
    parser.add_argument("--limit", type=int, default=250, help="commands the bot may add")
    parser.add_argument(
        "--first", action="append", default=[], help="scripted commands, e.g. 'k 3'"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    seed = Seed.parse(args.seed)
    game = Game.new(seed, args.level, args.rank, args.class_id)
    recorder = Recorder(game, seed.canonical, args.level, args.class_id, args.rank)
    for text in args.first:
        recorder.submit(decode_command(text))
    play(game, recorder.submit, args.limit)
    args.out.write_text(dumps(recorder.recording), "utf-8", newline="\n")
    state = "dead" if game.dead else f"alive, {len(game.monsters)} monsters left"
    print(f"{args.out}: {len(recorder.recording.commands)} commands, {state}")


if __name__ == "__main__":
    main()
