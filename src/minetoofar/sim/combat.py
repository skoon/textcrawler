"""Hit resolution (GDD 7.2): d20 against 10 + DEF, criticals double the dice, DR trims damage."""

from dataclasses import dataclass
from enum import Enum, auto

from minetoofar.core.rng import Rng

FACES = 20


class Outcome(Enum):
    MISS = auto()
    HIT = auto()
    CRIT = auto()


@dataclass(frozen=True)
class Stats:
    """What an attack needs to know about one combatant, already summed from kit and rank."""

    atk: int
    defense: int
    dr: int
    dice_n: int
    dice_sides: int
    dmg_flat: int
    attack_cost: int
    stuns: bool = False  # a critical hit with this weapon stuns


@dataclass(frozen=True)
class AttackResult:
    roll: int
    outcome: Outcome
    damage: int  # after DR; zero on a miss


def hit_outcome(roll: int, atk: int, defense: int, situational: int = 0) -> Outcome:
    if roll == 1:
        return Outcome.MISS
    if roll == FACES:
        return Outcome.CRIT
    hit = roll + atk + situational >= 10 + defense
    return Outcome.HIT if hit else Outcome.MISS


def hit_faces(atk: int, defense: int, situational: int = 0) -> int:
    """How many of the twenty faces hit; the tests use this to enumerate instead of sampling."""
    rolls = range(1, FACES + 1)
    return sum(hit_outcome(r, atk, defense, situational) is not Outcome.MISS for r in rolls)


def roll_damage(
    rng: Rng, stats: Stats, crit: bool, bonus_dice: tuple[int, int] = (0, 0), bonus_flat: int = 0
) -> int:
    """Weapon dice (doubled on a crit), then any bonus dice (not doubled), plus flat damage."""
    total = rng.dice(stats.dice_n * (2 if crit else 1), stats.dice_sides)
    count, sides = bonus_dice
    if count:
        total += rng.dice(count, sides)
    return total + stats.dmg_flat + bonus_flat


def apply_dr(raw: int, dr: int) -> int:
    return max(1, raw - dr)


def resolve_attack(
    rng: Rng,
    attacker: Stats,
    defender: Stats,
    situational: int = 0,
    *,
    auto_hit: bool = False,
    bonus_dice: tuple[int, int] = (0, 0),
    bonus_flat: int = 0,
) -> AttackResult:
    """Roll to hit, then damage. `auto_hit` still spends the d20 (a natural 20 is still a crit)."""
    roll = rng.below(FACES) + 1
    outcome = hit_outcome(roll, attacker.atk, defender.defense, situational)
    if auto_hit and outcome is Outcome.MISS:
        outcome = Outcome.HIT
    if outcome is Outcome.MISS:
        return AttackResult(roll, outcome, 0)
    raw = roll_damage(rng, attacker, outcome is Outcome.CRIT, bonus_dice, bonus_flat)
    return AttackResult(roll, outcome, apply_dr(raw, defender.dr))
