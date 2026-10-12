"""Turn game events into log lines (templates live in data/text/log.toml)."""

from textwrap import wrap

from minetoofar.content.docs import NAMES as DOCUMENT_NAMES
from minetoofar.content.text import Text
from minetoofar.core.grid import Tile
from minetoofar.sim.actors import PLAYER_ID
from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import (
    AbilityUsed,
    ArmorDamaged,
    Attacked,
    Blocked,
    Burrowed,
    DocumentRead,
    DoorOpened,
    Equipped,
    Event,
    Fled,
    GraveFall,
    Healed,
    HumanDefeated,
    ItemDropped,
    ItemPicked,
    ItemUsed,
    Killed,
    Moved,
    Noticed,
    PlayerDied,
    PoisonTick,
    RankSet,
    Refused,
    Rose,
    SeeHere,
    Spoke,
    Spotted,
    StatusApplied,
    StubbornInvoked,
    SupplyDropped,
    SupplyTaken,
    Surfaced,
    TorchBurnedOut,
    TorchChanged,
    TorchDropped,
    TrapDisarmed,
    TrapSpotted,
    TrapTriggered,
    ValuableCollected,
)

_KIND = {Outcome.HIT: "hit", Outcome.CRIT: "crit", Outcome.MISS: "miss"}


def wrap_log(messages: list[str], width: int, rows: int) -> list[str]:
    """The newest `rows` display rows: long messages wrap, continuation rows indented two spaces."""
    out: list[str] = []
    for message in messages[-rows:]:  # a message is at least one row, so older ones cannot show
        out += wrap(message, width, subsequent_indent="  ") or [""]
    return out[-rows:]


def _swing(e: Attacked, text: Text) -> str:
    kind = _KIND[e.outcome]
    if e.attacker == PLAYER_ID:
        if e.backstab:
            return text.line("you_backstab", target=e.target_name, damage=e.damage)
        return text.line(f"you_{kind}", target=e.target_name, damage=e.damage)
    return text.line(f"they_{kind}", attacker=e.attacker_name, damage=e.damage)


def describe(event: Event, text: Text, light_radius: int) -> str | None:
    """The line to show for an event, or None when it is not worth a log entry."""
    match event:
        case DoorOpened(by=by) if by == PLAYER_ID:
            return text.line("door_opened")
        case Blocked(reason=reason):
            return text.line(f"blocked_{reason}")
        case Moved(tile=Tile.EXIT):
            return text.line("on_exit")
        case TorchChanged(lit=True):
            return text.line("torch_lit", radius=light_radius)
        case TorchChanged():
            return text.line("torch_snuffed", radius=light_radius)
        case Attacked():
            return _swing(event, text)
        case Killed(name=name):
            return text.line("you_killed", target=name)
        case PlayerDied(killer=killer):
            return text.line("died", killer=killer)
        case StubbornInvoked():
            return text.line("stubborn")
        case ArmorDamaged(broken=True, armor=armor):
            return text.line("armor_broken", armor=armor)
        case Noticed(name=name):
            return text.line("noticed", name=name)
        case Spotted(name=name):
            return text.line("spotted", name=name)
        case RankSet(rank=rank):
            return text.line("rank_set", rank=rank)
        case AbilityUsed(name=name):
            return text.line("ability_used", name=name)
        case Refused(reason=reason):
            return text.line(f"refused_{reason}")
        case StatusApplied(actor=actor, status=status) if actor == PLAYER_ID:
            return text.line(f"status_you_{status}")
        case StatusApplied(name=name, status=status):
            return text.line(f"status_{status}", name=name)
        case PoisonTick(name=name, damage=damage):
            return text.line("poison_tick", name=name, damage=damage)
        case TrapSpotted(name=name):
            return text.line("trap_spotted", name=name)
        case TrapTriggered(name=name, damage=0):
            return text.line("trap_stunned", name=name)
        case TrapTriggered(name=name, damage=damage):
            return text.line("trap_triggered", name=name, damage=damage)
        case Spoke(name=name, text=said):
            return text.line("spoke", name=name, text=said)
        case Rose(name=name):
            return text.line("rose", name=name)
        case Surfaced(name=name):
            return text.line("surfaced", name=name)
        case Fled(name=name):
            return text.line("fled", name=name)
        case Burrowed(name=name):
            return text.line("burrowed", name=name)
        case TorchDropped():
            return text.line("torch_dropped")
        case GraveFall(damage=damage):
            return text.line("grave_fall", damage=damage)
        case TrapDisarmed(name=name):
            return text.line("trap_disarmed", name=name)
        case ItemPicked(name=name):
            return text.line("item_picked", name=name)
        case ValuableCollected(name=name, credit=credit):
            return text.line("valuable", name=name, credit=credit)
        case ItemUsed(name=name, charge=0):
            return text.line("item_used_prepaid", name=name)
        case ItemUsed(name=name, charge=charge):
            return text.line("item_used", name=name, charge=charge)
        case Healed(amount=amount):
            return text.line("healed", amount=amount)
        case ItemDropped(name=name):
            return text.line("item_dropped", name=name)
        case Equipped(name=name):
            return text.line("equipped", name=name)
        case SeeHere(names=names):
            return text.line("see_here", names=", ".join(names))
        case TorchBurnedOut():
            return text.line("torch_burned_out")
        case DocumentRead(kind=kind):
            return text.line("document_read", name=DOCUMENT_NAMES[kind])
        case SupplyDropped():
            return text.line("supply_inbound")
        case SupplyTaken(number=number, subtotal=sub, handling=fee, delivery=delivery):
            return text.line("supply_taken", number=number, total=sub + fee + delivery)
        case HumanDefeated(name=name):
            return text.line("human_defeated", name=name)
        case _:
            return None
