"""Tile grid and the movement rule shared by generation, FOV-adjacent code, and AI."""

from enum import IntEnum

from minetoofar.core.geometry import Pos


class Tile(IntEnum):
    SOLID = 0  # undug interior; never drawn
    WALL = 1  # constructed wall
    ROCK = 2  # natural cavern wall
    FLOOR = 3
    CAVE_FLOOR = 4
    DOOR = 5
    ENTRY = 6
    EXIT = 7
    DOOR_OPEN = 8  # a DOOR the player has opened; never produced by layout generation
    BRINE = 9  # walkable water: Eel home, soaks, can douse a lit torch
    RUBBLE = 10  # walkable, but a step onto it costs double
    GRAVESTONE = 11  # blocks movement, not sight
    MONUMENT = 12  # blocks movement and sight
    OPEN_GRAVE = 13  # walkable; falling in hurts and costs time


_WALKABLE = frozenset(
    {
        Tile.FLOOR, Tile.CAVE_FLOOR, Tile.DOOR, Tile.DOOR_OPEN, Tile.ENTRY, Tile.EXIT,
        Tile.BRINE, Tile.RUBBLE, Tile.OPEN_GRAVE,
    }
)  # fmt: skip
_BLOCKING = frozenset({Tile.SOLID, Tile.WALL, Tile.ROCK})
_BLOCKS_SIGHT = _BLOCKING | {Tile.DOOR, Tile.MONUMENT}
_DOORS = frozenset({Tile.DOOR, Tile.DOOR_OPEN})


def _table(members: frozenset[Tile]) -> bytes:
    return bytes(1 if i in members else 0 for i in range(256))  # indexed by raw tile byte


_WALK_BYTE = _table(_WALKABLE)
_BLOCK_BYTE = _table(_BLOCKING)
_DOOR_BYTE = _table(_DOORS)


def is_walkable(tile: Tile) -> bool:
    return tile in _WALKABLE


def blocks_sight(tile: Tile) -> bool:
    return tile in _BLOCKS_SIGHT


class Grid:
    def __init__(self, width: int, height: int, tiles: bytes | None = None) -> None:
        self.width = width
        self.height = height
        self._tiles = bytearray(tiles) if tiles is not None else bytearray(width * height)
        if len(self._tiles) != width * height:
            raise ValueError("tile buffer does not match grid size")

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get(self, x: int, y: int) -> Tile:
        if not self.in_bounds(x, y):
            raise IndexError(f"({x}, {y}) is outside {self.width}x{self.height}")
        return Tile(self._tiles[y * self.width + x])

    def set(self, x: int, y: int, tile: Tile) -> None:
        if not self.in_bounds(x, y):
            raise IndexError(f"({x}, {y}) is outside {self.width}x{self.height}")
        self._tiles[y * self.width + x] = tile

    def to_bytes(self) -> bytes:
        return bytes(self._tiles)

    def step_mult(self, x: int, y: int) -> int:
        """How many times the usual price a step onto (x, y) costs: Rubble doubles it."""
        return 2 if self._tiles[y * self.width + x] == Tile.RUBBLE else 1

    def can_step(self, pos: Pos, d: tuple[int, int]) -> bool:
        """Movement rule: destination walkable; diagonals may not cut corners or use doors.

        Reads the tile bytes directly: this is the inner loop of every distance map.
        """
        w, tiles = self.width, self._tiles
        nx, ny = pos.x + d[0], pos.y + d[1]
        if not (0 <= nx < w and 0 <= ny < self.height) or not _WALK_BYTE[tiles[ny * w + nx]]:
            return False
        if d[0] == 0 or d[1] == 0:
            return True
        if _DOOR_BYTE[tiles[pos.y * w + pos.x]] or _DOOR_BYTE[tiles[ny * w + nx]]:
            return False
        return not (_BLOCK_BYTE[tiles[pos.y * w + nx]] or _BLOCK_BYTE[tiles[ny * w + pos.x]])
