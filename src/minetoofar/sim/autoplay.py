"""A whole run played headlessly by the scripted bot: the balance simulator and the full-run
tests use it. Each level is played to the Down Shaft (or to a death), the pay slip is signed with
its defaults, and the Requisitions Desk is shopped from a priority list."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from minetoofar.content.balance import LEVELS
from minetoofar.core.seed import Seed
from minetoofar.sim.bot import CAREFUL, Memory, Policy, choose
from minetoofar.sim.checkin import Checkin
from minetoofar.sim.economy import title_key
from minetoofar.sim.game import Carry, Game

# What a sensible Associate buys first (GDD 8.5): hit points, healing, then armor and edge.
DESK_ORDER = (
    "wellness_seminar", "kit_bundle", "armor_plating", "hone_and_balance", "sharpening_service",
    "repair_plan",
)  # fmt: skip


# A careful Associate does not spend down to nothing: one bad level would put them in debt.
DESK_RESERVE = 8
LAST_RESERVE = 14  # before the last level a purchase has no later level to pay for itself in


@dataclass
class LevelLog:
    level: int
    outcome: str  # cleared | died | stalled
    gross: int
    adjusted: int
    net: int
    turns: int
    wallet: int  # after the slip
    debt: int
    bought: list[str] = field(default_factory=list)
    cause: str = ""  # what killed the player, when the level ended in a death


@dataclass
class RunLog:
    seed: str
    class_id: str
    outcome: str  # victory | death | stalled
    levels: list[LevelLog]
    score: int
    title: str
    wallet: int
    debt: int


def _shop(checkin: Checkin, order: Sequence[str], reserve: int = 0) -> list[str]:
    """Buy what the desk stocks, in priority order, never leaving less than `reserve` gold."""
    bought = []
    for key in order:
        for slot, stocked in enumerate(checkin.stock):
            if stocked != key or checkin.account.wallet - checkin.price(slot) < reserve:
                continue
            if checkin.buy(slot).ok:
                bought.append(key)
    return bought


def play_run(
    seed: Seed,
    class_id: str,
    policy: Policy = CAREFUL,
    rank: int = 1,
    order: Sequence[str] = DESK_ORDER,
    limit: int = 3000,
    reserve: int = DESK_RESERVE,
) -> RunLog:
    """Play levels 1 to 5 in turn; stops at the first death, or if a level will not finish."""
    carry: Carry | None = None
    levels: list[LevelLog] = []
    game: Game | None = None
    outcome = "victory"
    for level in range(1, LEVELS + 1):
        game = Game.new(seed, level, rank, class_id, carry=carry)
        sent = 0
        memory = Memory()
        while sent < limit and (command := choose(game, policy, memory)) is not None:
            game.submit(command)
            sent += 1
        if not game.dead and game.pos != game.spec.exit:
            outcome = "stalled"
            levels.append(LevelLog(level, "stalled", 0, 0, 0, game.total_turns, 0, 0))
            break
        slip = game.check_out()
        log = LevelLog(
            level, "died" if game.dead else "cleared", slip.gross, slip.adjusted, slip.net,
            game.ticks // 100, game.account.wallet, game.account.debt,
        )  # fmt: skip
        levels.append(log)
        if game.dead:
            log.cause = game.cause
            outcome = "death"
            break
        if level == LEVELS:
            break
        checkin = Checkin(game)
        keep = LAST_RESERVE if level == LEVELS - 1 else reserve
        log.bought = _shop(checkin, order, keep)
        carry = checkin.finish()
    assert game is not None
    score = game.score()
    return RunLog(
        seed.canonical, class_id, outcome, levels, score, title_key(score, game.economy),
        game.account.wallet, game.account.debt,
    )  # fmt: skip
