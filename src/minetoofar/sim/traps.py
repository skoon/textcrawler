"""Traps on the map. Only the Spring Trap exists so far, and the generator places none: they are
placed by tests until milestone 5 adds the real stage."""

from dataclasses import dataclass

from minetoofar.core.geometry import Pos


@dataclass
class Trap:
    pos: Pos
    kind: str  # a key of data/traps.toml
    revealed: bool = False  # hidden traps look like floor
    disarmed: bool = False  # a disarmed trap never triggers
