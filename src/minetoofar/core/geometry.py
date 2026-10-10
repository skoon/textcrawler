"""Positions, the eight directions, and integer distance."""

from typing import NamedTuple


class Pos(NamedTuple):
    x: int
    y: int

    def step(self, d: tuple[int, int]) -> "Pos":
        return Pos(self.x + d[0], self.y + d[1])


# Clockwise from north. Direction order is also the AI tie-break order (GDD 7.7).
DIRS8: tuple[tuple[int, int], ...] = (
    (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1),
)  # fmt: skip


def octile(a: Pos, b: Pos) -> int:
    dx, dy = abs(a.x - b.x), abs(a.y - b.y)
    return 14 * min(dx, dy) + 10 * abs(dx - dy)


def direction_to(src: Pos, dst: Pos) -> tuple[int, int]:
    """The sign of each axis: the compass direction from src toward dst, (0, 0) if equal."""
    return ((dst.x > src.x) - (dst.x < src.x), (dst.y > src.y) - (dst.y < src.y))


def in_rear_arc(attacker: Pos, target: Pos, facing: tuple[int, int]) -> bool:
    """True when `attacker` stands in the three tiles opposite `target`'s facing (GDD 7.4)."""
    toward = direction_to(target, attacker)
    if toward == (0, 0):
        return False
    behind = DIRS8.index((-facing[0], -facing[1]))
    return (DIRS8.index(toward) - behind) % 8 in (0, 1, 7)
