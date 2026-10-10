"""Immutable generator output and its canonical text dump (the hashed, golden-tested form)."""

import hashlib
from dataclasses import dataclass

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.core.seed import GEN_VERSION

TILE_CHARS: dict[Tile, str] = {
    Tile.SOLID: " ",
    Tile.WALL: "#",
    Tile.ROCK: "%",
    Tile.FLOOR: ".",
    Tile.CAVE_FLOOR: ",",
    Tile.DOOR: "+",
    Tile.ENTRY: "<",
    Tile.EXIT: ">",
    Tile.DOOR_OPEN: "/",
    Tile.BRINE: "~",
    Tile.RUBBLE: ":",
    Tile.GRAVESTONE: "T",
    Tile.MONUMENT: "H",
    Tile.OPEN_GRAVE: "u",
}


@dataclass(frozen=True)
class Spawn:
    kind: str
    pos: Pos
    state: str  # asleep | idle | buried | submerged
    facing: tuple[int, int]  # one of DIRS8; rolled on its own stream
    speech: tuple[tuple[str, str], ...] = ()  # a Rogue Human's lines, (event, text)
    pack: int = 0  # members of one Vermin pack share a number; 0 means alone


@dataclass(frozen=True)
class Room:
    id: int
    x: int
    y: int
    w: int
    h: int
    cave: bool
    anchor: Pos


@dataclass(frozen=True)
class LevelSpec:
    seed: str
    level: int
    width: int
    height: int
    tiles: bytes
    rooms: tuple[Room, ...]
    entry: Pos
    exit: Pos
    attempt: int

    def dump(self) -> str:
        lines = [
            "AMTF-LEVEL",
            f"gen_version {GEN_VERSION}",
            f"seed {self.seed}",
            f"level {self.level}",
            f"size {self.width} {self.height}",
            f"attempt {self.attempt}",
            f"entry {self.entry.x} {self.entry.y}",
            f"exit {self.exit.x} {self.exit.y}",
            f"rooms {len(self.rooms)}",
        ]
        for r in self.rooms:
            kind = "cave" if r.cave else "rect"
            lines.append(f"room {r.id} {r.x} {r.y} {r.w} {r.h} {kind} {r.anchor.x} {r.anchor.y}")
        lines.append("map")
        for y in range(self.height):
            row = self.tiles[y * self.width : (y + 1) * self.width]
            lines.append("".join(TILE_CHARS[Tile(t)] for t in row))
        return "\n".join(lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dump().encode("ascii")).hexdigest()
