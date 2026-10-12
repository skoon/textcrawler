"""Text for the status panel (GDD 5.1). Pure functions: no Textual, so tests need no terminal."""

from textwrap import wrap

from minetoofar.content.gamedata import UPGRADE_RANK
from minetoofar.content.text import Text
from minetoofar.core.geometry import Pos, octile
from minetoofar.gen.desk import Memo
from minetoofar.sim.actors import modifier
from minetoofar.sim.checkin import Checkin, FieldReport
from minetoofar.sim.economy import Line, Slip
from minetoofar.sim.game import Game
from minetoofar.sim.items import KIT, TORCH
from minetoofar.sim.supply import Invoice
from minetoofar.sim.views import GameView, HeroView, MonsterView
from minetoofar.ui.glyphs import GlyphSet, hp_bar

WIDTH = 24  # inner width of the 28-column panel (border and padding take four)
BAR_CELLS = 12
NEARBY_SHOWN = 5


def nearby_lines(
    monsters: tuple[MonsterView, ...],
    player: Pos,
    glyphs: GlyphSet,
    sensed: tuple[MonsterView, ...] = (),
) -> list[str]:
    """Up to five enemies, the ones in view first (nearest first, with HP), then the ones the
    Tracker senses through walls (GDD 5.1), shown as `~ Name` since they cannot be inspected."""

    def nearest(group: tuple[MonsterView, ...]) -> list[MonsterView]:
        return sorted(group, key=lambda m: (octile(player, m.pos), m.id))

    out = []
    for m in nearest(monsters):
        hp = f"{m.hp}/{m.max_hp}"
        room = WIDTH - 2 - 1 - len(hp)
        out.append(f"{glyphs.monsters[m.kind]} {m.name[:room].ljust(room)} {hp}")
    out += [f"~ {m.name}"[:WIDTH] for m in nearest(sensed)]
    return out[:NEARBY_SHOWN]


def _ability_line(view: GameView) -> str:
    ab = view.hero.ability
    if not ab.unlocked:
        state = f"Rk {ab.unlock_rank}"
    else:
        state = "rdy" if ab.ready else f"{ab.cooldown_turns}t"
    return f"[a] {ab.name}  {state}"


def _light_line(view: GameView) -> str:
    if view.torch_lit:
        return f"Light: Torch {view.torch_turns}t ({view.light_radius})"
    return f"Light: Lamp ({view.light_radius})"


def _pack_line(view: GameView) -> str:
    """Kits and torches by name, everything else as a count; the pack screen has the rest."""
    count = {KIT: 0, TORCH: 0}
    other = 0
    for p in view.pack:
        if p.id in count:
            count[p.id] += p.qty
        else:
            other += p.qty
    return f"Kits {count[KIT]}  Torches {count[TORCH]}" + (f"  +{other}" if other else "")


def status_lines(view: GameView, glyphs: GlyphSet, share_code: str) -> list[str]:
    hero = view.hero
    armor = f"Armor {hero.armor_dur}/{hero.armor_max}" + (" BROKEN" if hero.armor_dur <= 0 else "")
    lines = [
        f"{hero.name} the {hero.class_name}".ljust(20) + f"Rk{hero.rank}",
        f"HP {hp_bar(hero.hp, hero.max_hp, BAR_CELLS, glyphs)} {hero.hp}/{hero.max_hp}",
        f"DEF {hero.defense}  ATK {hero.atk:+d}  DMG {hero.damage}",
        armor,
        _light_line(view),
        _ability_line(view),
        _pack_line(view),
        f"Gold {view.gold}g  Debt {view.debt}g",
    ]
    nearby = nearby_lines(view.monsters, view.player, glyphs, view.sensed)
    if nearby:
        lines += ["Nearby", *nearby]
    return [*lines, f"Turn {view.turn}", f"Seed {share_code}"]


SHEET_WIDTH = 44


def _ability_text(game: Game, text: Text) -> str:
    ab = game.data.abilities[game.data.classes[game.player.class_id].ability]
    up = game.player.rank >= UPGRADE_RANK
    value, charges = (ab.value_up, ab.charges_up) if up else (ab.value, ab.charges)
    turns = (ab.cooldown_ticks_up if up else ab.cooldown_ticks) // 100
    if ab.kind == "cleave":
        penalty = f"-{value} ATK" if value else "no penalty"
        return text.line("ability_cleave", penalty=penalty, turns=turns)
    if ab.kind == "coat":
        return text.line("ability_coat", charges=charges, damage=value, turns=turns)
    return text.line("ability_dual_strike", bonus=value, turns=turns)


def sheet_lines(game: Game, text: Text) -> list[str]:
    """The character sheet (`c`): attributes, derived numbers, kit, and what the class can do."""
    hero = game.view().hero
    c = game.data.classes[game.player.class_id]
    ability = hero.ability
    state = (
        f"unlocks at Rank {ability.unlock_rank}"
        if not ability.unlocked
        else "ready"
        if ability.ready
        else f"{ability.cooldown_turns} turns to go"
    )
    lines = [
        f"{hero.name} the {hero.class_name}".ljust(SHEET_WIDTH - len(f"Rank {hero.rank}"))
        + f"Rank {hero.rank}",
        f"HP {hero.hp}/{hero.max_hp}",
        f"STR {c.strength} ({modifier(c.strength):+d})   "
        f"DEX {c.dexterity} ({modifier(c.dexterity):+d})",
        f"ATK {hero.atk:+d}   DEF {hero.defense}   DR {hero.dr}   DMG {hero.damage}",
        "",
        f"Main hand   {hero.weapon}",
        f"Off hand    {hero.offhand or '(empty)'}",
        f"Head        {hero.head}",
        f"Body        {hero.body}  {hero.armor_dur}/{hero.armor_max}",
        f"Trinket     {hero.trinket or '(none)'}",
    ]
    if hero.offhand_attack:
        lines.append(f"Off-hand attack: {hero.offhand_attack}")
    lines += ["", text.line(f"signature_{hero.signature}"), ""]
    lines += [f"Ability: {ability.name} ({state})", _ability_text(game, text)]
    return lines


PACK_WIDTH = 44


def pack_lines(view: GameView, text: Text) -> list[str]:
    """The pack screen: what is worn, then one lettered line per slot (a, b, c ...)."""
    hero = view.hero
    lines = [
        f"Main hand   {hero.weapon}",
        f"Off hand    {hero.offhand or '(empty)'}",
        f"Head        {hero.head}",
        f"Body        {hero.body}  {hero.armor_dur}/{hero.armor_max}",
        f"Trinket     {hero.trinket or '(none)'}",
        "",
    ]
    if not view.pack:
        return [*lines, text.line("inventory_empty")]
    for p in view.pack:
        letter = chr(ord("a") + p.index)
        if p.category == "consumable":
            price = f"{p.charge}g each" if p.charge else "prepaid"
            lines.append(f"{letter}  {p.name} x{p.qty} ({price})")
        elif p.category == "armor":
            lines.append(f"{letter}  {p.name}  {p.dur}/{p.dur_max}")
        else:
            lines.append(f"{letter}  {p.name}")
    return lines


SLIP_WIDTH = 60


def _dotted(label: str, value: str, indent: int = 2) -> str:
    room = SLIP_WIDTH - indent - len(value) - 2
    label = label[:room].rstrip()
    dots = "·" * max(2, room - len(label))
    return f"{' ' * indent}{label} {dots} {value}"


def _gold(n: int, sign: str = "") -> str:
    return f"{sign}{n}g"


def slip_lines(
    slip: Slip,
    text: Text,
    hero: HeroView,
    work_order: str,
    total: int,
    numbered: bool = False,
) -> list[str]:
    """The pay slip (GDD 5.2). With `numbered`, each line a coupon may be spent on gets [n]."""
    posthumous = slip.posthumous
    lines = [
        text.line("slip_head"),
        text.line("slip_order", number=slip.level, total=total, work_order=work_order),
    ]
    who = text.line("slip_associate", name=hero.name, class_name=hero.class_name, rank=hero.rank)
    num = text.line("slip_number", number=slip.level)
    lines += [who + " " * max(1, SLIP_WIDTH - len(who) - len(num)) + num, ""]
    lines.append(text.line("slip_gross"))
    lines += [_dotted(line.label, _gold(line.owed)) for line in slip.gross_lines]
    lines += [_dotted(text.line("slip_gross_total"), _gold(slip.gross)), ""]
    lines.append(text.line("slip_adjustments"))
    eligible = [line for line in slip.adjustments if line.key != "carried"]
    for line in slip.adjustments:
        mark = f"[{eligible.index(line) + 1}] " if numbered and line in eligible else ""
        lines.append(_dotted(mark + line.label, _gold(line.amount, "-"), 2))
        lines += [text.line("slip_waived", why=w, gold=g) for w, g in line.waivers]
    lines.append(_dotted(text.line("slip_adjusted_total"), _gold(slip.adjusted, "-")))
    lines += [
        "",
        _dotted(text.line("slip_net"), _gold(abs(slip.net), "+" if slip.net >= 0 else "-"), 0),
    ]
    wallet = text.line("slip_wallet", before=slip.wallet_before, after=slip.wallet_after)
    lines += [wallet + "   " + text.line("slip_owing", debt=slip.debt_after), ""]
    lines.append(text.line("slip_thanks_posthumous" if posthumous else "slip_thanks"))
    return lines


def coupon_targets(slip: Slip) -> list[Line]:
    """The adjustment lines a coupon may be spent on, in the order the screen numbers them."""
    return [line for line in slip.adjustments if line.key != "carried"]


def _dots(label: str, value: str, width: int, indent: int = 0) -> str:
    room = width - indent - len(value) - 2
    label = label[:room].rstrip()
    return f"{' ' * indent}{label} {'·' * max(2, room - len(label))} {value}"


REPORT_WIDTH = 60


def report_lines(
    report: FieldReport, text: Text, order_name: str, total: int, final: bool = False
) -> list[str]:
    """The field report (GDD 5.3); the last level's has no desk to restock for."""
    w = REPORT_WIDTH
    human = text.line("report_retrieved" if report.human_down else "report_at_large")
    lines = [
        text.line("report_title", number=report.level, total=total),
        _dots(text.line("report_order", number=report.level, name=order_name),
              text.line("report_closed"), w),
        "",
        _dots(text.line("report_undead"), str(report.undead), w),
        _dots(text.line("report_beasts"), str(report.beasts), w),
        _dots(text.line("report_human", name=report.human), human, w),
        _dots(text.line("report_valuables"), str(report.valuables), w),
        _dots(text.line("report_turns"), str(report.turns), w),
        "",
    ]  # fmt: skip
    if report.promoted_to:
        lines.append(text.line("report_promotion", rank=report.promoted_to))
        if report.unlocked:
            lines.append(text.line("report_unlock", ability=report.unlocked))
    if not final:
        lines.append(text.line("report_wellness", hp=report.hp, max_hp=report.max_hp))
        stock = ", ".join(f"{name} x{qty}" for name, qty in report.issued)
        lines.append(
            text.line("report_issue", items=stock) if stock else text.line("report_issue_none")
        )
    return [*lines, "", text.line("report_keys")]


MEMO_WIDTH = 56


def memo_lines(memo: Memo, text: Text) -> list[str]:
    """The company memo (GDD 5.3), wrapped to its box."""
    lines = [memo.subject, ""]
    for part in memo.lines:
        lines += wrap(part, MEMO_WIDTH) + [""]
    return [*lines, text.line("memo_keys")]


DESK_WIDTH = 64


def desk_lines(checkin: Checkin, text: Text, message: str = "") -> list[str]:
    """The Requisitions Desk (GDD 5.3): numbered offers, or a note that it is closed."""
    standing = text.line("desk_good" if checkin.open else "desk_hold")
    lines = [text.line("desk_title", wallet=checkin.account.wallet, standing=standing), ""]
    for slot in range(len(checkin.stock)):
        offer = checkin.offer(slot)
        price = text.line("desk_sold") if slot in checkin.sold else f"{offer.price}g"
        lines.append(_dots(f"[{slot + 1}] {offer.name} ({offer.blurb})", price, DESK_WIDTH))
    notes = [text.line("desk_repair_note")]
    if not checkin.open:
        notes.insert(0, text.line("desk_hold_note"))
    if message:
        notes.append(message)
    lines.append("")
    for note in notes:
        lines += wrap(note, DESK_WIDTH)
    return lines


INVOICE_WIDTH = 64


def invoice_lines(
    number: int, inv: Invoice, cursor: int, text: Text, handling_pct: int
) -> list[str]:
    """The supply drop invoice (GDD 8.5): a line per item with a check box, the totals, the keys."""
    w = INVOICE_WIDTH
    lines = [text.line("invoice_title", number=number)]
    for i, row in enumerate(inv.rows):
        box = "[x]" if row.taken else "[ ]"
        lines.append(
            _dots(f"{'>' if i == cursor else ' '} {box} {i + 1} {row.label}", f"{row.total}g", w)
        )
    if not inv.rows:
        lines.append(text.line("invoice_empty"))
    lines += [
        "",
        _dots("  " + text.line("invoice_subtotal"), f"{inv.subtotal}g", w),
        _dots("  " + text.line("invoice_handling", pct=handling_pct), f"{inv.handling}g", w),
        _dots("  " + text.line("invoice_delivery"), f"{inv.delivery}g", w),
        _dots("  " + text.line("invoice_total"), f"{inv.total}g", w),
        "",
        text.line("invoice_keys"),
    ]
    return lines
