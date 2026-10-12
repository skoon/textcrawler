"""Folding events into the ledger (plan 2.4): only what costs or earns gold is kept."""

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.sim.events import (
    HumanDefeated,
    ItemUsed,
    Moved,
    StatusApplied,
    StubbornInvoked,
    TorchDropped,
    TrapTriggered,
    ValuableCollected,
)
from minetoofar.sim.ledger import Ledger, Salvage, Use, fold
from tests.helpers import DATA


def folded(*events: object) -> Ledger:
    led = Ledger()
    for e in events:
        fold(led, e, DATA)  # type: ignore[arg-type]
    return led


def test_valuables_of_one_kind_merge_and_keep_first_seen_order() -> None:
    led = folded(
        ValuableCollected("rough_gem", "Rough Gem", 4),
        ValuableCollected("silver_nugget", "Silver Nugget", 2),
        ValuableCollected("rough_gem", "Rough Gem", 4),
    )
    assert led.salvage == [
        Salvage("rough_gem", "Rough Gem", 4, 2),
        Salvage("silver_nugget", "Silver Nugget", 2, 1),
    ]


def test_uses_merge_per_item_and_charge() -> None:
    led = folded(
        ItemUsed("patch_up_kit", "Patch-Up Kit", 5),
        ItemUsed("patch_up_kit", "Patch-Up Kit", 3),
        ItemUsed("patch_up_kit", "Patch-Up Kit", 5),
        ItemUsed("torch", "Torch", 2),
    )
    assert led.used == [
        Use("patch_up_kit", "Patch-Up Kit", 5, 2),
        Use("patch_up_kit", "Patch-Up Kit", 3, 1),
        Use("torch", "Torch", 2, 1),
    ]


def test_every_trap_counts_and_a_cave_in_adds_shoring() -> None:
    at = Pos(1, 1)
    led = folded(
        TrapTriggered(at, "Spring Trap", 5, "spring_trap"),
        TrapTriggered(at, "Tripwire Charge", 6, "tripwire_charge"),
        TrapTriggered(at, "Stun Charge", 0, "stun_charge"),
    )
    assert led.traps == 3 and led.tripwires == 1


def test_a_dropped_torch_and_stubborn_are_remembered() -> None:
    led = folded(TorchDropped(), TorchDropped(), StubbornInvoked(), StubbornInvoked())
    assert led.torches_dropped == 2 and led.stubborn is True


def test_only_the_players_clock_ins_are_billed() -> None:
    led = folded(
        StatusApplied(0, "Hale", "clocked_in"),
        StatusApplied(0, "Hale", "stunned"),
        StatusApplied(4, "Miner", "clocked_in"),
    )
    assert led.clock_ins == 1


def test_defeating_a_rogue_human_earns_the_bounty() -> None:
    assert folded(HumanDefeated("Foreman Grimsby")).bounty is True


def test_other_events_change_nothing() -> None:
    assert folded(Moved(Pos(1, 1), Tile.FLOOR)) == Ledger()
