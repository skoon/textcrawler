"""The gold economy (GDD 8.6, 8.8): a pure function from a level's ledger and the account to a
pay slip. Whole gold only; rounding is always up."""

from dataclasses import dataclass, replace

from minetoofar.content.balance import EconomyParams
from minetoofar.sim.ledger import Ledger

# Slip order: the incident lines come after the bills. The incidentals are what the Property
# Damage Waiver and the Lanyard may forgive; Hazard Pay and the Uniform Recovery Fee never are.
INCIDENTALS = ("torch_dropped", "hazard_surcharge", "shoring", "timecard")
HAZARDS = ("hazard_surcharge", "shoring")
TITLES = ("terminated", "probationary", "valued", "senior", "employee")


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


@dataclass(frozen=True)
class Account:
    wallet: int = 0
    debt: int = 0
    repair_plan: bool = False  # the next repair line is halved
    hazard_waiver: bool = False  # this level's Hazard Surcharge and Shoring Damage
    damage_waiver: bool = False  # this level's incidentals, up to a cap
    coupons: int = 0

    @property
    def on_hold(self) -> bool:
        """In debt: the Requisitions Desk is closed (GDD 8.6)."""
        return self.debt > 0


@dataclass(frozen=True)
class Choices:
    """What the player decides on the slip screen."""

    repair: bool = True  # decline repair to keep the gold and the damage
    coupons: tuple[str, ...] = ()  # one adjustment line key per coupon spent


@dataclass(frozen=True)
class Line:
    key: str
    label: str
    amount: int
    waivers: tuple[tuple[str, int], ...] = ()  # (what waived it, gold)

    @property
    def owed(self) -> int:
        return self.amount - sum(gold for _, gold in self.waivers)


@dataclass(frozen=True)
class Slip:
    level: int
    posthumous: bool
    gross_lines: tuple[Line, ...]
    adjustments: tuple[Line, ...]
    gross: int
    adjusted: int
    net: int
    wallet_before: int
    wallet_after: int
    debt_after: int
    repaired: bool  # the armor was restored to full
    account: Account  # as it stands after the slip


def _gross(led: Ledger, p: EconomyParams) -> list[Line]:
    lines = [] if led.died else [Line("base", "Base Job Fee", p.base_fee)]
    if led.graveyard:
        lines.append(Line("premium", "Hazard Premium", p.hazard_premium))
    if led.bounty:
        lines.append(Line("bounty", "Unauthorized Personnel Retrieval Bounty", p.bounty))
    for s in led.salvage:
        label = f"Salvage Credit: {s.name} x{s.count} @{s.credit}g"
        lines.append(Line(f"salvage:{s.kind}", label, s.credit * s.count))
    return lines


def _counted(label: str, n: int) -> str:
    return f"{label} x{n}" if n > 1 else label


def _bills(led: Ledger, choices: Choices) -> list[Line]:
    lines: list[Line] = []
    r = led.repair
    if r is not None and r.missing > 0 and choices.repair:
        cost = _ceil_div(r.missing * r.rate, 4)
        lines.append(Line("repair", f"Armor repair: {r.name}, {r.missing} pts", cost))
    for u in led.used:
        tail = " (prepaid)" if u.charge == 0 else ""
        label = f"Consumables: {u.name} x{u.count} @{u.charge}g{tail}"
        lines.append(Line(f"used:{u.item}:{u.charge}", label, u.charge * u.count))
    lines += [Line(f"supply:{i}", label, gold) for i, (label, gold) in enumerate(led.supply, 1)]
    return lines


def _incidents(led: Ledger, p: EconomyParams) -> list[Line]:
    lines: list[Line] = []
    if led.torches_dropped:
        label = _counted("Dropped torch", led.torches_dropped)
        lines.append(Line("torch_dropped", label, led.torches_dropped * p.dropped_torch))
    if led.traps:
        label = _counted("Hazard Surcharge", led.traps)
        lines.append(Line("hazard_surcharge", label, led.traps * p.hazard_surcharge))
    if led.tripwires:
        label = _counted("Shoring Damage", led.tripwires)
        lines.append(Line("shoring", label, led.tripwires * p.shoring_damage))
    if led.stubborn:
        lines.append(Line("hazard_pay", "Hazard Pay (Stubborn invoked)", p.hazard_pay))
    if led.clock_ins:
        label = _counted("Timecard Irregularity", led.clock_ins)
        lines.append(Line("timecard", label, min(led.clock_ins * p.timecard_fee, p.timecard_cap)))
    if led.died:
        lines.append(Line("uniform", "Uniform Recovery Fee", p.uniform_fee))
    return lines


def _waive(lines: list[Line], key: str, why: str, most: int) -> int:
    """Forgive up to `most` gold of the line `key`; returns what was forgiven."""
    for i, line in enumerate(lines):
        if line.key == key:
            gold = min(most, line.owed)
            if gold:
                lines[i] = replace(line, waivers=(*line.waivers, (why, gold)))
            return gold
    return 0


def _apply_waivers(
    lines: list[Line], led: Ledger, account: Account, choices: Choices, p: EconomyParams
) -> Account:
    """Waivers and coupons in the fixed order of GDD 8.6."""
    plan_used = False
    if account.repair_plan:
        repair = next((line for line in lines if line.key == "repair"), None)
        if repair is not None:
            plan_used = True
            _waive(lines, "repair", "Repair Plan", repair.owed - _ceil_div(repair.owed, 2))
    if account.hazard_waiver:
        for key in HAZARDS:
            _waive(lines, key, "Hazard Waiver", p.damage_waiver_cap * 100)
    if account.damage_waiver:
        left = p.damage_waiver_cap
        for key in INCIDENTALS:
            left -= _waive(lines, key, "Property Damage Waiver", left)
    if led.lanyard:
        for key in INCIDENTALS:
            line = next((line for line in lines if line.key == key), None)
            if line is not None and 0 < line.owed <= p.lanyard_max:
                _waive(lines, key, "Laminated Lanyard", line.owed)
                break
    for key in choices.coupons:
        _waive(lines, key, "Coupon", p.coupon_value)
    return replace(
        account,
        repair_plan=account.repair_plan and not plan_used,
        hazard_waiver=False,
        damage_waiver=False,
        coupons=account.coupons - len(choices.coupons),
    )


def compute_slip(led: Ledger, account: Account, choices: Choices, p: EconomyParams) -> Slip:
    """The pay slip for one level (or the Posthumous Pay Slip when the ledger says died)."""
    if len(choices.coupons) > account.coupons:
        raise ValueError(f"{len(choices.coupons)} coupons chosen, {account.coupons} held")
    lines = [*_bills(led, choices), *_incidents(led, p)]
    if account.debt:
        lines.append(Line("carried", "Balance carried forward", account.debt))
        fee = _ceil_div(account.debt * p.late_fee_pct, 100)
        lines.append(Line("late_fee", "Administrative late fee", fee))
    known = {line.key for line in lines if line.key != "carried"}  # old debt takes no coupon
    for key in choices.coupons:
        if key not in known:
            raise ValueError(f"no such line to take a coupon off: {key!r}")
    after = _apply_waivers(lines, led, account, choices, p)
    gross_lines = _gross(led, p)
    gross = sum(line.owed for line in gross_lines)
    adjusted = sum(line.owed for line in lines)
    net = gross - adjusted
    if net >= 0:
        wallet, debt = account.wallet + net, 0
    else:
        paid = min(account.wallet, -net)
        wallet, debt = account.wallet - paid, -net - paid
    repair = next((line for line in lines if line.key == "repair"), None)
    return Slip(
        led.level, led.died, tuple(gross_lines), tuple(lines), gross, adjusted, net,
        account.wallet, wallet, debt, repair is not None,
        replace(after, wallet=wallet, debt=debt),
    )  # fmt: skip


def score(account: Account, levels_cleared: int, bounties: int, params: EconomyParams) -> int:
    """GDD 8.8: wealth plus 10 a level and 5 a bounty."""
    return (
        account.wallet - account.debt
        + params.level_score * levels_cleared
        + params.bounty_score * bounties
    )  # fmt: skip


def title_key(points: int, p: EconomyParams) -> str:
    """Which final title a score earns (the words live in the text tables)."""
    cuts = (p.title_probationary, p.title_valued, p.title_senior, p.title_employee)
    return TITLES[sum(points >= cut for cut in cuts)]
