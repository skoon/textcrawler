"""What happened on a level that costs or earns gold (GDD 8.6, plan 2.4). The pay slip is a pure
function of this record, so it never has to look at the game."""

from dataclasses import dataclass, field, replace

from minetoofar.content.gamedata import GameData
from minetoofar.sim.actors import PLAYER_ID
from minetoofar.sim.events import (
    Event,
    HumanDefeated,
    ItemUsed,
    StatusApplied,
    StubbornInvoked,
    TorchDropped,
    TrapTriggered,
    ValuableCollected,
)


@dataclass(frozen=True)
class Salvage:
    """Valuables of one kind turned in at check-in."""

    kind: str
    name: str
    credit: int  # gold each
    count: int


@dataclass(frozen=True)
class Use:
    """Consumables used from one stack; `charge` is the gold billed per item (0: prepaid)."""

    item: str
    name: str
    charge: int
    count: int


@dataclass(frozen=True)
class Repair:
    """The worn body armor: `rate` is quarter-gold per missing point."""

    name: str
    missing: int
    rate: int


@dataclass
class Ledger:
    level: int = 1
    graveyard: bool = False  # Hazard Premium
    died: bool = False  # the Posthumous Pay Slip
    bounty: bool = False  # the level's Rogue Human was defeated
    salvage: list[Salvage] = field(default_factory=list)
    used: list[Use] = field(default_factory=list)
    traps: int = 0  # triggered, Tripwire Charges included
    tripwires: int = 0  # the cave-ins among them
    torches_dropped: int = 0
    clock_ins: int = 0
    undead_kills: int = 0  # for the field report
    beast_kills: int = 0
    stubborn: bool = False
    repair: Repair | None = None
    lanyard: bool = False  # a Laminated Lanyard is worn
    supply: list[tuple[str, int]] = field(default_factory=list)  # (invoice label, gold)


def fold(led: Ledger, event: Event, data: GameData) -> None:
    """Record the economic meaning of one event, if it has any."""
    match event:
        case ValuableCollected(kind=kind, name=name, credit=credit):
            for i, s in enumerate(led.salvage):
                if s.kind == kind:
                    led.salvage[i] = replace(s, count=s.count + 1)
                    return
            led.salvage.append(Salvage(kind, name, credit, 1))
        case ItemUsed(id=item, name=name, charge=charge):
            for i, u in enumerate(led.used):
                if u.item == item and u.charge == charge:
                    led.used[i] = replace(u, count=u.count + 1)
                    return
            led.used.append(Use(item, name, charge, 1))
        case TrapTriggered(kind=kind):
            led.traps += 1
            led.tripwires += data.traps[kind].cave_in
        case TorchDropped():
            led.torches_dropped += 1
        case StubbornInvoked():
            led.stubborn = True
        case StatusApplied(actor=actor, status="clocked_in") if actor == PLAYER_ID:
            led.clock_ins += 1
        case HumanDefeated():
            led.bounty = True
