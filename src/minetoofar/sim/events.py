"""Commands the UI sends to the game and the events the game reports back."""

from dataclasses import dataclass
from enum import StrEnum

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.sim.combat import Outcome


@dataclass(frozen=True, slots=True)
class Move:
    dx: int
    dy: int


@dataclass(frozen=True, slots=True)
class Run:
    dx: int
    dy: int


@dataclass(frozen=True, slots=True)
class Wait:
    pass


@dataclass(frozen=True, slots=True)
class ToggleTorch:
    pass


@dataclass(frozen=True, slots=True)
class SetRank:
    """Debug: jump to a Rank and heal fully. No time passes."""

    rank: int


@dataclass(frozen=True, slots=True)
class UseAbility:
    """Use the class's active ability (one per class in v1)."""


@dataclass(frozen=True, slots=True)
class Disarm:
    """Rogue only: disarm the revealed trap on the adjacent tile in this direction."""

    dx: int
    dy: int


Command = Move | Run | Wait | ToggleTorch | SetRank | UseAbility | Disarm


class BlockReason(StrEnum):
    WALL = "wall"
    CORNER = "corner"
    DOOR = "door"
    TRAP = "trap"  # a run will not step onto a trap you know about
    OCCUPIED = "occupied"  # something unseen (buried, submerged) is in the way


@dataclass(frozen=True, slots=True)
class Moved:
    pos: Pos
    tile: Tile


@dataclass(frozen=True, slots=True)
class DoorOpened:
    pos: Pos
    by: int = 0  # actor id; 0 is the player


@dataclass(frozen=True, slots=True)
class Blocked:
    """A refused move. It costs no time."""

    pos: Pos
    reason: BlockReason


@dataclass(frozen=True, slots=True)
class Waited:
    pass


@dataclass(frozen=True, slots=True)
class TorchChanged:
    lit: bool


@dataclass(frozen=True, slots=True)
class RankSet:
    rank: int


@dataclass(frozen=True, slots=True)
class Attacked:
    attacker: int
    attacker_name: str
    target: int
    target_name: str
    roll: int
    outcome: Outcome
    damage: int  # after DR; zero on a miss
    backstab: bool = False  # the Rogue's bonus dice were added


@dataclass(frozen=True, slots=True)
class Killed:
    actor: int
    name: str


@dataclass(frozen=True, slots=True)
class PlayerDied:
    killer: str


@dataclass(frozen=True, slots=True)
class StubbornInvoked:
    pass


@dataclass(frozen=True, slots=True)
class ArmorDamaged:
    armor: str
    durability: int
    maximum: int
    broken: bool  # true only on the hit that breaks it


@dataclass(frozen=True, slots=True)
class Noticed:
    """A monster woke up or caught sight of the player."""

    actor: int
    name: str


@dataclass(frozen=True, slots=True)
class Spotted:
    """A monster came into the player's view for the first time."""

    actor: int
    name: str


@dataclass(frozen=True, slots=True)
class TorchDropped:
    """A lit torch was lost (entering Brine, or a critical hit)."""


@dataclass(frozen=True, slots=True)
class GraveFall:
    pos: Pos
    damage: int


@dataclass(frozen=True, slots=True)
class Spoke:
    """A Rogue Human says a line (speech is rolled at generation, GDD 9.6)."""

    actor: int
    name: str
    text: str


@dataclass(frozen=True, slots=True)
class Rose:
    """A buried Miner climbs out of its grave."""

    actor: int
    name: str


@dataclass(frozen=True, slots=True)
class Surfaced:
    """A submerged Eel erupts to ambush."""

    actor: int
    name: str


@dataclass(frozen=True, slots=True)
class Fled:
    """A Badger breaks and runs."""

    actor: int
    name: str


@dataclass(frozen=True, slots=True)
class Burrowed:
    """A fleeing Badger digs away for good."""

    actor: int
    name: str


@dataclass(frozen=True, slots=True)
class Refused:
    """A command that could not be carried out. It costs no time."""

    reason: str  # locked | cooldown | no_target | not_rogue | no_trap


@dataclass(frozen=True, slots=True)
class AbilityUsed:
    name: str


@dataclass(frozen=True, slots=True)
class StatusApplied:
    actor: int
    name: str
    status: str


@dataclass(frozen=True, slots=True)
class PoisonTick:
    actor: int
    name: str
    damage: int


@dataclass(frozen=True, slots=True)
class TrapSpotted:
    pos: Pos
    name: str


@dataclass(frozen=True, slots=True)
class TrapTriggered:
    pos: Pos
    name: str
    damage: int
    kind: str = ""  # the trap's data key, for the pay slip's surcharges


@dataclass(frozen=True, slots=True)
class TrapDisarmed:
    pos: Pos
    name: str


Event = (
    Moved | DoorOpened | Blocked | Waited | TorchChanged | RankSet | Attacked | Killed
    | PlayerDied | StubbornInvoked | ArmorDamaged | Noticed | Spotted | Refused | AbilityUsed
    | StatusApplied | PoisonTick | TrapSpotted | TrapTriggered | TrapDisarmed | TorchDropped
    | GraveFall | Spoke | Rose | Surfaced | Fled | Burrowed
)  # fmt: skip
