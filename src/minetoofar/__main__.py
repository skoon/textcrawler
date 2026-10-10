"""Command line: play a seeded level, view it, print its canonical dump or hash, audit glyphs."""

import argparse
import os
import secrets
import sys
from collections.abc import Sequence

from minetoofar import __version__
from minetoofar.content.balance import LEVELS
from minetoofar.content.gamedata import load_gamedata
from minetoofar.core.seed import GEN_VERSION, Seed, SeedError, seed_text_from_entropy
from minetoofar.gen.layout import generate_level
from minetoofar.gen.world import STAGES, Stage, generate_world
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
    p.add_argument("--view", action="store_true", help="open the level viewer (all revealed)")
    p.add_argument("--ui-selftest", action="store_true", help="start the game headless, then exit")
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
    if not 1 <= args.level <= LEVELS:
        parser.error(f"--level must be 1-{LEVELS}")
    if not 1 <= args.rank <= 5:
        parser.error("--rank must be 1-5")
    try:
        seed = Seed.parse(args.seed or seed_text_from_entropy(secrets.token_bytes(8)))
    except SeedError as err:
        parser.error(f"invalid --seed: {err}")
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
    from minetoofar.ui.game_app import run, selftest

    if args.ui_selftest:
        print(selftest(seed, args.level, glyphs))
        return 0
    class_id = args.class_id
    if class_id is None:
        from minetoofar.ui.select import choose_class

        class_id = choose_class()
        if class_id is None:
            return 0
    run(seed, args.level, glyphs, args.rank, class_id)
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


if __name__ == "__main__":
    raise SystemExit(main())
