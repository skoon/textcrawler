"""The Rogue Human (GDD 9.6, 10.4 step 7): one per level, in a lair far enough along the way to
the exit, with the speech it will use rolled now so a seed always shows the same words."""

import hashlib
from dataclasses import dataclass

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.speech import load_speech, render_lines
from minetoofar.core.geometry import DIRS8, Pos, octile
from minetoofar.core.grid import Grid
from minetoofar.core.pathing import distance_map
from minetoofar.core.seed import Seed
from minetoofar.gen.features import Features
from minetoofar.gen.level_spec import LevelSpec, Room, Spawn
from minetoofar.gen.rooms import floor_tiles
from minetoofar.gen.theme import Theme

LAIRS = {"foreman_grimsby": "foreman_office", "prospector_vane": "prospector_camp"}
NOT_A_LAIR = ("entry", "exit", "flooded", "mausoleum")  # the guarantees every level keeps


class HumanError(RuntimeError):
    pass


@dataclass(frozen=True)
class Humans:
    seed: str
    level: int
    kind: str
    room_id: int
    room_kind: str
    pos: Pos
    facing: tuple[int, int]
    mood: str
    tic: str
    speech: tuple[tuple[str, str], ...]  # (event, line) in a fixed order

    def spawn(self) -> Spawn:
        return Spawn(self.kind, self.pos, "idle", self.facing, self.speech)

    def dump(self) -> str:
        lines = [
            "AMTF-HUMANS",
            f"seed {self.seed}",
            f"level {self.level}",
            f"human {self.kind}",
            f"room {self.room_id} {self.room_kind}",
            f"pos {self.pos.x} {self.pos.y}",
            f"facing {self.facing[0]} {self.facing[1]}",
            f"mood {self.mood}",
            f"tic {self.tic}",
        ]
        lines += [f"line {event} {text}" for event, text in self.speech]
        return "\n".join(lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dump().encode("ascii")).hexdigest()


def _stand_tile(grid: Grid, room: Room) -> Pos | None:
    """The plain floor tile nearest the room's anchor: where the human waits."""
    tiles = floor_tiles(grid, room)
    return min(tiles, key=lambda p: (octile(p, room.anchor), p.y, p.x)) if tiles else None


def generate_humans(
    seed: Seed, level: int, spec: LevelSpec, features: Features, theme: Theme
) -> Humans:
    """`spec` is the level with its features laid in."""
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1-{LEVELS}, got {level}")
    p = load_balance().humans
    grid = Grid(spec.width, spec.height, spec.tiles)
    dist = distance_map(grid, spec.entry)
    pct = p.last_level_distance_pct if level == LEVELS else p.distance_pct
    threshold = dist[spec.exit] * pct // 100

    options: list[tuple[int, int, int, Room, Pos]] = []
    for room in spec.rooms:
        stand = _stand_tile(grid, room)
        if features.room_kinds[room.id] in NOT_A_LAIR or stand is None or stand not in dist:
            continue
        options.append((dist[stand], room.anchor.y, room.anchor.x, room, stand))
    if not options:
        raise HumanError("no room can be a lair")
    options.sort(key=lambda o: (o[0], o[1], o[2]))
    far_enough = [o for o in options if o[0] >= threshold]
    # The first room that is far enough (ties: lowest y, x); if none is, the farthest there is.
    _, _, _, room, stand = far_enough[0] if far_enough else options[-1]

    rng = seed.rng().derive("level", level, "human")
    facing = rng.pick(DIRS8)
    book = load_speech()
    speech = render_lines(
        book, theme.human, theme.mood, theme.tic_roll,
        seed.rng().derive("level", level, "speech"), p.tic_one_in,
    )  # fmt: skip
    tic = book.tics[theme.human][theme.tic_roll % len(book.tics[theme.human])]
    return Humans(
        spec.seed, level, theme.human, room.id, LAIRS[theme.human], stand, facing, theme.mood,
        tic, tuple(speech.items()),
    )  # fmt: skip
