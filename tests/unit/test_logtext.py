from minetoofar.content.text import load_text
from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.sim.combat import Outcome
from minetoofar.sim.events import (
    AbilityUsed,
    ArmorDamaged,
    Attacked,
    Blocked,
    BlockReason,
    Burrowed,
    DoorOpened,
    Fled,
    GraveFall,
    Killed,
    Moved,
    Noticed,
    PlayerDied,
    PoisonTick,
    RankSet,
    Refused,
    Rose,
    Spoke,
    Spotted,
    StatusApplied,
    StubbornInvoked,
    Surfaced,
    TorchChanged,
    TorchDropped,
    TrapDisarmed,
    TrapSpotted,
    TrapTriggered,
    Waited,
)
from minetoofar.ui.logtext import describe

TEXT = load_text()


def test_quiet_events_say_nothing() -> None:
    assert describe(Moved(Pos(1, 1), Tile.FLOOR), TEXT, 4) is None
    assert describe(Waited(), TEXT, 4) is None


def test_door_and_refusals_have_lines() -> None:
    assert describe(DoorOpened(Pos(1, 1)), TEXT, 4) == TEXT.line("door_opened")
    for reason in BlockReason:
        assert describe(Blocked(Pos(0, 0), reason), TEXT, 4) == TEXT.line(f"blocked_{reason}")


def test_stepping_on_the_down_shaft_is_noted() -> None:
    assert describe(Moved(Pos(1, 1), Tile.EXIT), TEXT, 4) == TEXT.line("on_exit")


def test_torch_lines_report_the_radius() -> None:
    assert describe(TorchChanged(True), TEXT, 8) == TEXT.line("torch_lit", radius=8)
    assert describe(TorchChanged(False), TEXT, 4) == TEXT.line("torch_snuffed", radius=4)


def swing(attacker: int, outcome: Outcome, damage: int = 0) -> Attacked:
    mine = attacker == 0
    return Attacked(
        attacker, "Hale" if mine else "Shambling Miner", 1 if mine else 0,
        "Shambling Miner" if mine else "Hale", 12, outcome, damage,
    )  # fmt: skip


def test_the_players_swings() -> None:
    assert describe(swing(0, Outcome.HIT, 8), TEXT, 4) == TEXT.line(
        "you_hit", target="Shambling Miner", damage=8
    )
    assert describe(swing(0, Outcome.CRIT, 19), TEXT, 4) == TEXT.line(
        "you_crit", target="Shambling Miner", damage=19
    )
    assert describe(swing(0, Outcome.MISS), TEXT, 4) == TEXT.line(
        "you_miss", target="Shambling Miner"
    )


def test_the_monsters_swings() -> None:
    assert describe(swing(1, Outcome.HIT, 3), TEXT, 4) == TEXT.line(
        "they_hit", attacker="Shambling Miner", damage=3
    )
    assert describe(swing(1, Outcome.CRIT, 9), TEXT, 4) == TEXT.line(
        "they_crit", attacker="Shambling Miner", damage=9
    )
    assert describe(swing(1, Outcome.MISS), TEXT, 4) == TEXT.line(
        "they_miss", attacker="Shambling Miner"
    )


def test_kills_deaths_stubborn_and_notices() -> None:
    assert describe(Killed(1, "Shambling Miner"), TEXT, 4) == TEXT.line(
        "you_killed", target="Shambling Miner"
    )
    assert describe(PlayerDied("Shambling Miner"), TEXT, 4) == TEXT.line(
        "died", killer="Shambling Miner"
    )
    assert describe(StubbornInvoked(), TEXT, 4) == "You are STUBBORN. HR has been notified."
    assert describe(Noticed(1, "Shambling Miner"), TEXT, 4) == TEXT.line(
        "noticed", name="Shambling Miner"
    )
    assert describe(Spotted(1, "Shambling Miner"), TEXT, 4) == TEXT.line(
        "spotted", name="Shambling Miner"
    )
    assert describe(RankSet(3), TEXT, 4) == TEXT.line("rank_set", rank=3)


def test_armor_is_only_mentioned_when_it_breaks() -> None:
    assert describe(ArmorDamaged("Boiler Suit", 17, 18, False), TEXT, 4) is None
    assert describe(ArmorDamaged("Boiler Suit", 0, 18, True), TEXT, 4) == TEXT.line(
        "armor_broken", armor="Boiler Suit"
    )


def test_doors_opened_by_monsters_are_not_the_players_to_report() -> None:
    assert describe(DoorOpened(Pos(1, 1), by=1), TEXT, 4) is None
    assert describe(DoorOpened(Pos(1, 1)), TEXT, 4) == TEXT.line("door_opened")


def test_a_backstab_has_its_own_line() -> None:
    stab = Attacked(0, "Rook", 1, "Cave Vermin", 12, Outcome.HIT, 11, True)
    assert describe(stab, TEXT, 4) == TEXT.line("you_backstab", target="Cave Vermin", damage=11)
    assert describe(swing(0, Outcome.MISS), TEXT, 4) == TEXT.line(
        "you_miss", target="Shambling Miner"
    )


def test_abilities_poison_and_refusals() -> None:
    assert describe(AbilityUsed("Cleave"), TEXT, 4) == TEXT.line("ability_used", name="Cleave")
    assert describe(StatusApplied(1, "Shambling Miner", "poisoned"), TEXT, 4) == TEXT.line(
        "status_poisoned", name="Shambling Miner"
    )
    assert describe(PoisonTick(1, "Shambling Miner", 2), TEXT, 4) == TEXT.line(
        "poison_tick", name="Shambling Miner", damage=2
    )
    for reason in ("locked", "cooldown", "no_target", "not_rogue", "no_trap"):
        assert describe(Refused(reason), TEXT, 4) == TEXT.line(f"refused_{reason}")


def test_traps() -> None:
    pos = Pos(2, 2)
    assert describe(TrapSpotted(pos, "Spring Trap"), TEXT, 4) == TEXT.line(
        "trap_spotted", name="Spring Trap"
    )
    assert describe(TrapTriggered(pos, "Spring Trap", 6), TEXT, 4) == TEXT.line(
        "trap_triggered", name="Spring Trap", damage=6
    )
    assert describe(TrapDisarmed(pos, "Spring Trap"), TEXT, 4) == TEXT.line(
        "trap_disarmed", name="Spring Trap"
    )
    assert describe(Blocked(pos, BlockReason.TRAP), TEXT, 4) == TEXT.line("blocked_trap")


def test_monster_events_have_their_lines() -> None:
    assert describe(Rose(1, "Shambling Miner"), TEXT, 4) == TEXT.line(
        "rose", name="Shambling Miner"
    )
    assert describe(Surfaced(1, "Blind Ore-Eel"), TEXT, 4) == TEXT.line(
        "surfaced", name="Blind Ore-Eel"
    )
    assert describe(Fled(1, "Gem Badger"), TEXT, 4) == TEXT.line("fled", name="Gem Badger")
    assert (
        describe(Burrowed(1, "Gem Badger"), TEXT, 4)
        == "The Gem Badger has retired to a private burrow."
    )
    assert describe(Spoke(1, "Foreman Grimsby", "Clock in!"), TEXT, 4) == (
        'Foreman Grimsby says: "Clock in!"'
    )


def test_terrain_events_have_their_lines() -> None:
    assert describe(TorchDropped(), TEXT, 4) == TEXT.line("torch_dropped")
    assert describe(GraveFall(Pos(1, 1), 3), TEXT, 4) == TEXT.line("grave_fall", damage=3)
    assert describe(Blocked(Pos(1, 1), BlockReason.OCCUPIED), TEXT, 4) == TEXT.line(
        "blocked_occupied"
    )


def test_statuses_on_the_player_read_differently_from_those_on_monsters() -> None:
    assert describe(StatusApplied(0, "Hale", "stunned"), TEXT, 4) == TEXT.line("status_you_stunned")
    assert describe(StatusApplied(0, "Hale", "clocked_in"), TEXT, 4) == TEXT.line(
        "status_you_clocked_in"
    )
    assert describe(StatusApplied(1, "Shambling Miner", "poisoned"), TEXT, 4) == TEXT.line(
        "status_poisoned", name="Shambling Miner"
    )


def test_a_stun_charge_says_stunned_instead_of_a_damage_number() -> None:
    assert describe(
        TrapTriggered(Pos(1, 1), "Stun Charge", 0, "stun_charge"), TEXT, 4
    ) == TEXT.line("trap_stunned", name="Stun Charge")


def test_wrap_log_keeps_short_messages_whole_and_returns_the_newest_rows() -> None:
    from minetoofar.ui.logtext import wrap_log

    assert wrap_log(["one", "two", "three"], 20, 2) == ["two", "three"]
    assert wrap_log(["one"], 20, 4) == ["one"]


def test_wrap_log_wraps_long_messages_with_an_indented_continuation() -> None:
    from minetoofar.ui.logtext import wrap_log

    said = 'Foreman Grimsby says: "Per my last memo, you are on the clock and then some."'
    rows = wrap_log([said], 60, 4)
    assert len(rows) == 2 and all(len(r) <= 60 for r in rows)
    assert rows[0].startswith("Foreman Grimsby says:") and rows[1].startswith("  ")
    assert " ".join(r.strip() for r in rows) == said


def test_wrap_log_shows_the_tail_of_a_wrapped_message_when_rows_run_out() -> None:
    from minetoofar.ui.logtext import wrap_log

    said = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    rows = wrap_log(["earlier", said], 20, 2)
    assert len(rows) == 2 and rows[-1].strip().endswith("lambda")
    assert "earlier" not in rows


def test_wrap_log_breaks_a_word_longer_than_the_panel() -> None:
    from minetoofar.ui.logtext import wrap_log

    assert wrap_log(["x" * 25], 10, 4) == ["x" * 10, "  " + "x" * 8, "  " + "x" * 7]
