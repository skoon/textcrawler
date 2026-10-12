"""Command line: play a seeded level, view it, print its canonical dump or hash, audit glyphs."""

import argparse
import os
import secrets
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path

from minetoofar import __version__
from minetoofar.content.balance import LEVELS
from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.seed import GEN_VERSION, Seed, SeedError, seed_text_from_entropy
from minetoofar.gen.layout import generate_level
from minetoofar.gen.world import STAGES, Stage, generate_world
from minetoofar.persist.errors import SaveError
from minetoofar.persist.paths import resolve_save_dir, save_dir
from minetoofar.ui.glyphs import GLYPH_TABLE, auto_glyph_name


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="minetoofar", description="A Mine Too Far")
    p.add_argument("--seed", help="seed text or share code (default: a fresh random seed)")
    p.add_argument("--level", type=int, default=1, help=f"level to show, 1-{LEVELS}")
    p.add_argument("--glyphs", choices=["auto", "unicode", "ascii"], default="auto")
    p.add_argument(
        "--stage", choices=list(STAGES), default="layout", help="what --dump/--hash cover"
    )
    p.add_argument("--dump", action="store_true", help="print the canonical dump and exit")
    p.add_argument("--hash", action="store_true", help="print the dump's sha256 and exit")
    p.add_argument("--glyph-test", action="store_true", help="print every glyph in both sets")
    p.add_argument(
        "--class", dest="class_id", choices=list(load_gamedata().classes),
        help="skip the class select screen",
    )  # fmt: skip
    p.add_argument("--rank", type=int, default=1, help="start at this Rank, 1-5 (debug)")
    p.add_argument("--save-dir", help="where the saved run and records live (default: see README)")
    p.add_argument("--where", action="store_true", help="print the folder saves go in and exit")
    p.add_argument("--view", action="store_true", help="open the level viewer (all revealed)")
    p.add_argument("--ui-selftest", action="store_true", help="start the game headless, then exit")
    p.add_argument("--autoplay", action="store_true", help="play a whole run with the bot (check)")
    p.add_argument(
        "--save-selftest", choices=["write", "read"], help="write or read a save (release check)"
    )
    p.add_argument("--version", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"minetoofar {__version__} (generator {GEN_VERSION})")
        return 0
    if args.glyph_test:
        _glyph_test()
        return 0
    if args.where:
        try:
            print(resolve_save_dir(args.save_dir))
        except SaveError as err:
            print(f"minetoofar: {err}", file=sys.stderr)
            return 2
        return 0
    if args.save_selftest == "read":
        return _save_selftest(None, "", args.save_dir, read=True)
    if not 1 <= args.level <= LEVELS:
        parser.error(f"--level must be 1-{LEVELS}")
    if not 1 <= args.rank <= 5:
        parser.error("--rank must be 1-5")
    try:
        seed = Seed.parse(args.seed or seed_text_from_entropy(secrets.token_bytes(8)))
    except SeedError as err:
        parser.error(f"invalid --seed: {err}")
    if args.autoplay or args.save_selftest:
        from minetoofar.release_check import autoplay_line

        class_id = args.class_id or "fighter"
        if args.autoplay:
            print(autoplay_line(seed, class_id))
            return 0
        return _save_selftest(seed, class_id, args.save_dir, read=False)
    if args.dump or args.hash:
        stage = _stage(seed, args.level, args.stage)
        out = stage.sha256 + "\n" if args.hash else stage.dump()
        sys.stdout.flush()
        sys.stdout.buffer.write(out.encode("ascii"))  # bytes: no newline translation on Windows
        sys.stdout.buffer.flush()
        return 0
    glyphs = args.glyphs
    if glyphs == "auto":
        glyphs = auto_glyph_name(sys.platform, os.environ, sys.stdout.encoding)
    # late imports: --dump/--hash must not need Textual
    if args.view:
        from minetoofar.ui.app import run_viewer

        run_viewer(seed, args.level, glyphs)
        return 0
    from minetoofar.ui.game_app import run, run_saved, selftest

    if args.ui_selftest:
        print(selftest(seed, args.level, glyphs))
        return 0
    try:
        folder = save_dir(args.save_dir)
    except SaveError as err:
        print(f"minetoofar: {err}", file=sys.stderr)
        return 2
    plain = args.seed is None and args.class_id is None and args.level == 1 and args.rank == 1
    if not plain:
        # a run named on the command line: it never replaces a saved run unless you say so
        class_id = args.class_id
        if class_id is None:
            from minetoofar.ui.select import choose_class

            class_id = choose_class()
            if class_id is None:
                return 0
        run(seed, args.level, glyphs, args.rank, class_id, saves=folder)
        return 0
    from minetoofar.ui.select import choose_class
    from minetoofar.ui.title import choose_start

    while True:
        choice, saved = choose_start(folder)
        if choice == "quit":
            return 0
        if choice == "continue" and saved is not None:
            run_saved(saved, glyphs, folder)
            return 0
        class_id = choose_class()
        if class_id is not None:
            run(seed, 1, glyphs, 1, class_id, saves=folder, owns_slot=True)
            return 0


def _save_selftest(seed: Seed | None, class_id: str, folder: str | None, read: bool) -> int:
    from minetoofar.release_check import read_save_line, write_save_line

    try:
        where = save_dir(folder)
        print(
            read_save_line(where)
            if read or seed is None
            else write_save_line(seed, class_id, where)
        )
    except (SaveError, ValueError) as err:
        print(f"minetoofar: {err}", file=sys.stderr)
        return 2
    return 0


def _stage(seed: Seed, level: int, name: str) -> Stage:
    if name == "layout":
        return generate_level(seed, level)  # no need for the later stages
    return generate_world(seed, level).stage(name)


def _glyph_test() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"{'category':9} {'name':22} unicode  ascii")
    for category, name, uni, asc in GLYPH_TABLE:
        print(f"{category:9} {name:22} {uni:^7}  {asc:^5}")
    print("wall autotile (unicode): ▪║═╚║║╔╠═╝═╩╗╣╦╬")


def owns_console(processes: int, one_file: bool) -> bool:
    """Is this console window ours alone, as when the EXE is double-clicked? A one-file EXE is
    two processes (the bootstrap and the game); a shell that started it would be one more."""
    return processes <= (2 if one_file else 1)


def _own_window() -> bool:
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False
    import ctypes

    listed = (ctypes.c_uint * 8)()
    count = int(ctypes.windll.kernel32.GetConsoleProcessList(listed, 8))
    bundle = Path(getattr(sys, "_MEIPASS", sys.executable))
    one_file = (
        bundle.parent != Path(sys.executable).parent and bundle != Path(sys.executable).parent
    )
    return owns_console(count, one_file)


def hold_window(code: int, own_window: bool, wait: Callable[[str], str] = input) -> None:
    """After a failure in a window that will vanish, wait so the message can be read."""
    if code == 0 or not own_window:
        return
    try:
        wait("\nPress Enter to close this window. ")
    except EOFError:
        pass  # nothing to wait on: no keyboard


def _entry() -> int:
    try:
        code = main()
    except SystemExit as stop:  # argparse and friends
        code = stop.code if isinstance(stop.code, int) else int(stop.code is not None)
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        code = 1
    hold_window(code, _own_window())
    return code


if __name__ == "__main__":
    raise SystemExit(_entry())
