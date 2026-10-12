"""Supply crates and their invoices (GDD 8.5): only the lines you take are billed, plus 20%
Expedited Handling (rounded up) and a delivery fee once per crate."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from minetoofar.content.balance import SupplyParams
from minetoofar.content.gamedata import GameData
from minetoofar.core.geometry import Pos
from minetoofar.gen.drops import SupplyLine


@dataclass
class Crate:
    """A landed supply drop; what is left in it stays until you leave the level."""

    pos: Pos
    number: int
    lines: list[SupplyLine] = field(default_factory=list)
    delivery_billed: bool = False


@dataclass(frozen=True)
class InvoiceRow:
    label: str
    total: int
    taken: bool


@dataclass(frozen=True)
class Invoice:
    rows: tuple[InvoiceRow, ...]
    subtotal: int
    handling: int
    delivery: int

    @property
    def total(self) -> int:
        return self.subtotal + self.handling + self.delivery


def _tier_price(tier: int, p: SupplyParams) -> int:
    return (p.price_t1, p.price_t2, p.price_t3)[tier - 1]


def _tier(item: str, data: GameData) -> int:
    items = data.items
    table = {
        "weapon": items.weapons, "armor": items.armor, "shield": items.shields,
        "hat": items.hats, "trinket": items.trinkets,
    }[items.category(item)]  # fmt: skip
    return int(table[item].tier)  # type: ignore[attr-defined]


def line_price(line: SupplyLine, data: GameData, p: SupplyParams) -> int:
    """List price for stock; the flat tier price for equipment."""
    if line.item in data.items.consumables:
        return data.items.consumables[line.item].price * line.qty
    return _tier_price(_tier(line.item, data), p)


def _label(line: SupplyLine, data: GameData) -> str:
    name = data.items.name(line.item)
    if line.item in data.items.consumables:
        return f"{name} x{line.qty} @ {data.items.consumables[line.item].price}g"
    return f"{name} (T{_tier(line.item, data)})"


def invoice(
    lines: Sequence[SupplyLine],
    taken: Collection[int],
    delivery_due: bool,
    data: GameData,
    p: SupplyParams,
) -> Invoice:
    """The bill for taking the lines at the indexes in `taken`."""
    for i in taken:
        if not 0 <= i < len(lines):
            raise IndexError(f"no line {i} in a crate of {len(lines)}")
    rows = tuple(
        InvoiceRow(_label(ln, data), line_price(ln, data, p), i in taken)
        for i, ln in enumerate(lines)
    )
    subtotal = sum(r.total for r in rows if r.taken)
    handling = -(-subtotal * p.handling_pct // 100)
    delivery = p.delivery_fee if taken and delivery_due else 0
    return Invoice(rows, subtotal, handling, delivery)
