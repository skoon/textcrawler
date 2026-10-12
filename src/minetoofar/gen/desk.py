"""A check-in's Requisitions Desk stock and company memo (generation stage `desk`, GDD 5.3, 8.5).
Both are rolled from the seed alone, on `store/N`, so the desk after Level N is the same for
every player of the seed."""

import hashlib
from dataclasses import dataclass

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.desk import DeskItem, load_desk
from minetoofar.content.memos import MemoBook, load_memos
from minetoofar.core.seed import Seed
from minetoofar.gen.theme import generate_theme


@dataclass(frozen=True)
class Memo:
    sender: str
    subject: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class Desk:
    seed: str
    level: int  # the check-in comes after this level
    stock: tuple[str, ...]  # desk catalog keys, slot 1 first (always a bundle)
    memo: Memo | None  # None after the last level: there is no desk and no memo

    def dump(self) -> str:
        lines = ["AMTF-DESK", f"seed {self.seed}", f"level {self.level}"]
        lines.append("stock " + " ".join(self.stock))
        if self.memo is not None:
            lines += [f"from {self.memo.sender}", f"re {self.memo.subject}", *self.memo.lines]
        return "\n".join(lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dump().encode("ascii")).hexdigest()


def _policy(seed: Seed, check_in: int, book: MemoBook) -> tuple[int, int]:
    """Which policy line this memo states: a pair and a side. From the second memo on, half the
    time it is the other side of the pair the memo before it chose."""
    rng = seed.rng().derive("store", check_in, "policy")
    pair, side = rng.below(len(book.policies)), rng.below(2)
    if check_in > 1 and rng.chance(1, 2):
        before_pair, before_side = _policy(seed, check_in - 1, book)
        return before_pair, 1 - before_side
    return pair, side


def _memo(seed: Seed, level: int, book: MemoBook) -> Memo:
    rng = seed.rng().derive("store", level, "memo")
    graveyard = generate_theme(seed, level + 1).graveyard
    pair, side = _policy(seed, level, book)
    opener, reminder = rng.pick(book.openers), rng.pick(book.reminders)
    sender, subject, signoff = (
        rng.pick(book.senders),
        rng.pick(book.subjects),
        rng.pick(book.signoffs),
    )
    if graveyard:
        premium = load_balance().economy.hazard_premium
        notice = book.graveyard_notice.format(level=level + 1, premium=premium)
        subject += " (Graveyard Initiative)"
    else:
        notice = book.plain_notice.format(level=level + 1)
    return Memo(
        sender, f"RE: {subject}", (opener, book.policies[pair][side], reminder, notice, signoff)
    )


def _stock(seed: Seed, level: int, catalog: dict[str, DeskItem]) -> tuple[str, ...]:
    rng = seed.rng().derive("store", level)
    slots = load_balance().checkin.desk_slots
    bundles = [(k, i.weight) for k, i in catalog.items() if i.effect == "bundle"]
    rest = [(k, i.weight) for k, i in catalog.items() if i.effect != "bundle" and i.weight > 0]
    stock = [rng.weighted(bundles)]
    for _ in range(slots - 1):
        pick = rng.weighted(rest)
        rest = [(k, w) for k, w in rest if k != pick]
        stock.append(pick)
    return tuple(stock)


def generate_desk(seed: Seed, level: int) -> Desk:
    """The check-in after `level`. After the last level there is only the final slip."""
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1-{LEVELS}, got {level}")
    if level == LEVELS:
        return Desk(seed.canonical, level, (), None)
    return Desk(
        seed.canonical, level, _stock(seed, level, load_desk()), _memo(seed, level, load_memos())
    )
