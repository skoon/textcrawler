"""The playable screen: map, status panel, log, look mode, prompts, the character sheet, the death
report, and the too-small guard."""

import asyncio
import secrets
from collections.abc import Callable
from importlib import resources
from pathlib import Path

from rich.style import Style
from rich.text import Text as RichText
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Key, Resize
from textual.screen import ModalScreen
from textual.widgets import Static

from minetoofar.content.balance import LEVELS
from minetoofar.content.text import Text, load_text
from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.core.seed import Seed, seed_text_from_entropy
from minetoofar.persist.errors import SaveError
from minetoofar.persist.records import append_record, make_record
from minetoofar.persist.save import SavedRun, delete_save, has_save, write_save
from minetoofar.sim.checkin import Checkin, field_report
from minetoofar.sim.economy import Choices, title_key
from minetoofar.sim.events import (
    AtCrate,
    Command,
    Disarm,
    DocumentRead,
    DropItem,
    Equip,
    Move,
    TakeSupply,
    UseItem,
)
from minetoofar.sim.game import REMEMBERED, UNSEEN, VISIBLE, Carry, Game, GameView
from minetoofar.ui.glyphs import glyph_set
from minetoofar.ui.keymap import UiAction, lookup
from minetoofar.ui.logtext import describe, wrap_log
from minetoofar.ui.mapview import ITEM_STYLES, MapView, dim
from minetoofar.ui.panels import (
    coupon_targets,
    desk_lines,
    invoice_lines,
    memo_lines,
    pack_lines,
    report_lines,
    sheet_lines,
    slip_lines,
    status_lines,
)

MIN_SIZE = (80, 24)
PLAYER = ("@", Style(color="#ffffff", bold=True))
FACTION_STYLES = {
    "undead": Style(color="#7fb7e0"),
    "beast": Style(color="#e0a050"),
    "human": Style(color="#ffffff", bold=True),
}
SENSED = Style(color="#3a8fa0")  # dim cyan: sensed through a wall, not seen (GDD 5.4)
TRAP = Style(color="#e05050", bold=True)
TRAP_OFF = Style(color="#707070")
CRATE = Style(color="#d09040", bold=True)
LOG_KEPT = 200


def log_lines(rows: int) -> int:
    """Log panel height (GDD 5.1): four lines on the minimum screen, up to ten on a tall one."""
    return max(4, min(10, rows // 6))


def _plain(text: str) -> RichText:
    """Panel text without markup parsing, clipped with an ellipsis instead of wrapping."""
    return RichText(text, no_wrap=True, overflow="ellipsis")


class DeathScreen(ModalScreen[str]):
    """The incident report: R retries the seed, N starts a new one, Q quits."""

    CHOICES = {"r": "retry", "n": "new", "q": "quit", "escape": "quit"}

    def __init__(self, lines: list[str], title: str) -> None:
        super().__init__()
        self._lines = lines
        self._title = title

    def compose(self) -> ComposeResult:
        report = Static(RichText("\n".join(self._lines)), id="death")
        report.border_title = self._title
        yield report

    def on_key(self, event: Key) -> None:
        choice = self.CHOICES.get(event.key)
        event.stop()
        if choice:
            self.dismiss(choice)


class ReviewScreen(DeathScreen):
    """The end of a finished run: the performance review. N starts a new run, Q quits."""

    CHOICES = {"n": "new", "q": "quit", "escape": "quit"}


class SheetScreen(ModalScreen[None]):
    """The character sheet; any key closes it."""

    def __init__(self, lines: list[str], title: str) -> None:
        super().__init__()
        self._lines = lines
        self._title = title

    def compose(self) -> ComposeResult:
        sheet = Static(RichText("\n".join(self._lines)), id="sheet")
        sheet.border_title = self._title
        yield sheet

    def on_key(self, event: Key) -> None:
        event.stop()
        self.dismiss()


class HelpScreen(ModalScreen[None]):
    """The keys and the rules of the job; any key closes it."""

    def __init__(self, words: str, title: str) -> None:
        super().__init__()
        self._words, self._title = words, title

    def compose(self) -> ComposeResult:
        panel = Static(RichText(self._words), id="help")
        panel.border_title = self._title
        yield panel

    def on_key(self, event: Key) -> None:
        event.stop()
        self.dismiss()


class DocumentScreen(ModalScreen[None]):
    """A found document; any key closes it."""

    def __init__(self, words: str, title: str, keys: str) -> None:
        super().__init__()
        self._words, self._title, self._keys = words, title, keys

    def compose(self) -> ComposeResult:
        sheet = Static(RichText(self._words + "\n\n" + self._keys), id="document")
        sheet.border_title = self._title
        yield sheet

    def on_key(self, event: Key) -> None:
        event.stop()
        self.dismiss()


class PackScreen(ModalScreen[tuple[int, bool] | None]):
    """The pack. Viewing closes on any key; choosing (equip, use, drop) takes a slot letter, and
    a capital letter asks for the off hand. Escape cancels."""

    def __init__(self, lines: list[str], title: str, prompt: str, slots: int, pick: bool) -> None:
        super().__init__()
        self._lines, self._title, self._prompt = lines, title, prompt
        self._slots, self._pick = slots, pick

    def compose(self) -> ComposeResult:
        pack = Static(RichText("\n".join(self._lines)), id="pack")
        pack.border_title = self._title
        yield pack
        yield Static(RichText(self._prompt), id="packkeys")

    def on_key(self, event: Key) -> None:
        event.stop()
        char = event.character or ""
        slot = ord(char.lower()) - ord("a") if len(char) == 1 and char.isalpha() else -1
        if event.key == "escape" or not self._pick:
            self.dismiss(None)
        elif 0 <= slot < self._slots:
            self.dismiss((slot, char.isupper()))


class SlipScreen(ModalScreen[Choices]):
    """The pay slip (GDD 5.2). R toggles armor repair; with a coupon in hand a digit spends it on
    that numbered line (again to take it back); Enter signs for it."""

    def __init__(self, game: Game, text: Text, work_order: str) -> None:
        super().__init__()
        self._game, self._text, self._work_order = game, text, work_order
        self.repair = True
        self.picks: list[str] = []

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="slipbox"):
            yield Static(id="slip")
        yield Static(id="slipkeys")

    def on_mount(self) -> None:
        title = "slip_posthumous_title" if self._game.dead else "slip_title"
        self.query_one("#slipbox").border_title = self._text.line(title)
        self._draw()

    def _choices(self) -> Choices:
        live = {line.key for line in self._game.slip(Choices(repair=self.repair)).adjustments}
        return Choices(self.repair, tuple(k for k in self.picks if k in live))

    def _draw(self) -> None:
        game, t = self._game, self._text
        slip = game.slip(self._choices())
        held = game.account.coupons
        lines = slip_lines(slip, t, game.view().hero, self._work_order, LEVELS, numbered=held > 0)
        self.query_one("#slip", Static).update(RichText("\n".join(lines)))
        self.query_one("#slipkeys", Static).update(
            RichText(t.line("slip_keys_coupon" if held else "slip_keys"))
        )

    def on_key(self, event: Key) -> None:
        event.stop()
        if event.key == "enter":
            self.dismiss(self._choices())
            return
        if event.key in ("up", "down", "pageup", "pagedown"):
            box = self.query_one("#slipbox", VerticalScroll)
            {"up": box.scroll_up, "down": box.scroll_down, "pageup": box.scroll_page_up,
             "pagedown": box.scroll_page_down}[event.key](animate=False)  # fmt: skip
            return
        if event.key == "r":
            self.repair = not self.repair
        elif event.character and event.character.isdigit():
            targets = coupon_targets(self._game.slip(Choices(repair=self.repair)))
            n = int(event.character)
            if not 1 <= n <= len(targets):
                return
            key = targets[n - 1].key
            if key in self.picks:
                self.picks.remove(key)
            elif len(self.picks) < self._game.account.coupons:
                self.picks.append(key)
        else:
            return
        self._draw()


class ReportScreen(ModalScreen[str]):
    """The field report. Enter goes on to the pay slip; Escape signs the slip as it stands and
    skips to the memo."""

    def __init__(self, lines: list[str], title: str) -> None:
        super().__init__()
        self._lines, self._title = lines, title

    def compose(self) -> ComposeResult:
        report = Static(RichText("\n".join(self._lines[1:])), id="report")
        report.border_title = self._lines[0]
        yield report

    def on_key(self, event: Key) -> None:
        event.stop()
        if event.key == "enter":
            self.dismiss("slip")
        elif event.key == "escape":
            self.dismiss("skip")


class MemoScreen(ModalScreen[None]):
    """The company memo; Enter goes on to the Requisitions Desk."""

    def __init__(self, lines: list[str], title: str) -> None:
        super().__init__()
        self._lines, self._title = lines, title

    def compose(self) -> ComposeResult:
        memo = Static(RichText("\n".join(self._lines)), id="memo")
        memo.border_title = self._title
        yield memo

    def on_key(self, event: Key) -> None:
        event.stop()
        if event.key == "enter":
            self.dismiss()


class ConfirmScreen(ModalScreen[bool]):
    """A yes/no question in a box: Y says yes, N or Escape says no."""

    def __init__(self, lines: list[str]) -> None:
        super().__init__()
        self._lines = lines

    def compose(self) -> ComposeResult:
        yield Static(RichText("\n".join(self._lines)), id="menu")

    def on_key(self, event: Key) -> None:
        event.stop()
        if event.key == "y":
            self.dismiss(True)
        elif event.key in ("n", "escape"):
            self.dismiss(False)


class MenuScreen(ModalScreen[str]):
    """Escape in the game: Save & quit, or back to work."""

    def __init__(self, lines: list[str], title: str) -> None:
        super().__init__()
        self._lines, self._title = lines, title

    def compose(self) -> ComposeResult:
        menu = Static(RichText("\n".join(self._lines)), id="menu")
        menu.border_title = self._title
        yield menu

    def on_key(self, event: Key) -> None:
        event.stop()
        if event.key == "s":
            self.dismiss("save")
        elif event.key == "escape":
            self.dismiss("back")


class DeskScreen(ModalScreen[str]):
    """The Requisitions Desk (GDD 5.3): a digit buys that slot, Enter goes down the Shaft, S
    saves the run and quits."""

    def __init__(self, checkin: Checkin, text: Text) -> None:
        super().__init__()
        self.checkin, self._text = checkin, text
        self._message = ""

    def compose(self) -> ComposeResult:
        yield Static(id="desk")

    def on_mount(self) -> None:
        self._draw()

    def _draw(self) -> None:
        lines = desk_lines(self.checkin, self._text, self._message)
        keys = self._text.line(
            "desk_keys", slots=len(self.checkin.stock), next=self.checkin.level + 1
        )
        desk = self.query_one("#desk", Static)
        desk.update(RichText("\n".join([*lines[1:], "", keys])))
        desk.border_title = lines[0]

    def on_key(self, event: Key) -> None:
        event.stop()
        if event.key == "enter":
            self.dismiss("down")
        elif event.key == "s":
            self.dismiss("save")
        elif event.character and event.character.isdigit():
            slot = int(event.character) - 1
            if 0 <= slot < len(self.checkin.stock):
                self._buy(slot)

    def _buy(self, slot: int) -> None:
        got = self.checkin.buy(slot)
        if got.ok:
            name = self.checkin.offer(slot).name
            self._message = self._text.line("desk_bought", name=name)
        else:
            self._message = self._text.line(f"desk_refused_{got.reason}")
        self._draw()


class InvoiceScreen(ModalScreen[tuple[int, ...] | None]):
    """A supply drop's invoice (GDD 8.5): tick the lines to take, Enter accepts, Escape leaves."""

    def __init__(self, game: Game, text: Text) -> None:
        super().__init__()
        self._game, self._text = game, text
        self._taken: set[int] = set()
        self._cursor = 0

    def compose(self) -> ComposeResult:
        yield Static(id="invoice")

    def on_mount(self) -> None:
        self._draw()

    def _draw(self) -> None:
        crate = self._game.crate_here()
        assert crate is not None
        inv = self._game.crate_invoice(tuple(sorted(self._taken)))
        lines = invoice_lines(
            crate.number, inv, self._cursor, self._text, self._game.supply_params.handling_pct
        )
        box = self.query_one("#invoice", Static)
        box.update(RichText("\n".join(lines[1:])))
        box.border_title = lines[0]

    def _toggle(self, line: int) -> None:
        self._taken ^= {line}

    def on_key(self, event: Key) -> None:
        event.stop()
        crate = self._game.crate_here()
        count = len(crate.lines) if crate else 0
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            self.dismiss(tuple(sorted(self._taken)) or None)
        elif event.key in ("up", "k") and count:
            self._cursor = (self._cursor - 1) % count
        elif event.key in ("down", "j") and count:
            self._cursor = (self._cursor + 1) % count
        elif event.key == "space" and count:
            self._toggle(self._cursor)
        elif event.character and event.character.isdigit() and 1 <= int(event.character) <= count:
            self._cursor = int(event.character) - 1
            self._toggle(self._cursor)
        else:
            return
        self._draw()


class GameApp(App[None]):
    CSS = resources.files("minetoofar.ui").joinpath("theme.tcss").read_text("utf-8")

    def __init__(
        self,
        game: Game,
        glyphs: str,
        saves: Path | None = None,
        resume: SavedRun | None = None,
        owns_slot: bool = False,
    ) -> None:
        super().__init__()
        self.game = game
        self.saves = saves  # the folder a run saves in; None: no saving at all
        self.owns_slot = owns_slot or resume is not None  # the save on disk, if any, is this run's
        resumed_mid_level = resume is not None and resume.game is not None
        self._resumed_log = resume.log if resume is not None and resumed_mid_level else None
        self.glyph_name = glyphs
        self.text: Text = load_text()
        self.messages: list[str] = []
        self.look_pos: Pos | None = None
        self.pending: Callable[[], None] | None = None  # what a "y" answers, while a prompt is up
        self.start_rank = game.player.rank  # a retry begins where this level began
        self.arrival: Carry | None = None  # what came down the Shaft; None on the first level
        self.checkin: Checkin | None = None
        self.class_id = game.player.class_id
        if resume is not None:
            self.arrival, self.start_rank, self.class_id = (
                resume.arrival, resume.start_rank, resume.class_id,
            )  # fmt: skip

    def compose(self) -> ComposeResult:
        yield Static(id="too-small")
        with Vertical(id="game"):
            with Horizontal(id="top"):
                yield MapView(self.game.spec, glyph_set(self.glyph_name), id="map")
                status = Static(id="status")
                status.border_title = "Status"
                yield status
            panel = Static(id="log")
            panel.border_title = "Log"
            yield panel

    def on_mount(self) -> None:
        self.query_one(MapView).follows_focus = True
        self._begin()
        self._check_size(self.size.width, self.size.height)

    def on_resize(self, event: Resize) -> None:
        self._check_size(event.size.width, event.size.height)
        self.query_one("#log").styles.height = log_lines(event.size.height) + 2
        self._refresh_log()

    def _check_size(self, width: int, height: int) -> None:
        small = width < MIN_SIZE[0] or height < MIN_SIZE[1]
        self.screen_stack[0].set_class(small, "too-small")  # the game screen, even under a modal
        if small:
            line = self.text.line(
                "too_small", min_w=MIN_SIZE[0], min_h=MIN_SIZE[1], w=width, h=height
            )
            self.query_one("#too-small", Static).update(_plain(line))

    # -- a run begins ----------------------------------------------------------------------

    def _begin(self) -> None:
        """Show the current game from its first turn: title, welcome line, camera, panels."""
        spec = self.game.spec
        info = self.text.levels[spec.level - 1]
        map_view = self.query_one(MapView)
        map_view.show(spec, glyph_set(self.glyph_name))
        map_view.border_title = f"{info.name} · L{spec.level}"
        self.messages, self.look_pos, self.pending = [], None, None
        if self._resumed_log is not None:
            self.messages = [*self._resumed_log, self.text.line("resumed")]
            self._resumed_log = None
            self._refresh_log()
        else:
            self._say(
                self.text.line(
                    "welcome", number=spec.level, total=LEVELS, work_order=info.work_order
                )
            )
        self._sync()

    def _start_level(self, seed: Seed, level: int) -> None:
        self.game = Game.new(seed, level, self.start_rank, self.class_id, carry=self.arrival)
        self._begin()

    def _restart(self, seed: Seed) -> None:
        self._start_level(seed, self.game.spec.level)

    def _descend(self, forced: bool) -> None:
        """Take the Down Shaft: field report, pay slip, memo and desk. With `forced`, the debug
        skip: the books are settled quietly, you are promoted, and the next level begins."""
        player, level = self.game.player, self.game.spec.level
        if not forced and self.game.grid.get(player.pos.x, player.pos.y) != Tile.EXIT:
            self._say(self.text.line("descend_none"))
        elif forced and level >= LEVELS:
            self._say(self.text.line("descend_last"))
        elif forced:
            self.game.check_out()
            self._next_level(Checkin(self.game).finish())
        else:
            self._show_report()

    def _show_report(self) -> None:
        spec = self.game.spec
        name = self.text.levels[spec.level - 1].name
        final = spec.level >= LEVELS
        lines = report_lines(field_report(self.game), self.text, name, LEVELS, final=final)
        self.push_screen(ReportScreen(lines, ""), self._reported)

    def _reported(self, choice: str | None) -> None:
        if choice == "skip":
            self._signed(Choices())
        else:
            self._show_slip()

    def _show_slip(self) -> None:
        spec = self.game.spec
        order = self.text.levels[spec.level - 1].work_order
        self.push_screen(SlipScreen(self.game, self.text, order), self._signed)

    def _signed(self, choices: Choices | None) -> None:
        """The slip is accepted: the wallet is paid, then the level ends one way or another."""
        self.game.check_out(choices)
        if self.game.dead:
            self._death_report()
        elif self.game.spec.level >= LEVELS:
            self._review()
        else:
            self._memo()

    def _memo(self) -> None:
        self.checkin = Checkin(self.game)
        memo = self.checkin.memo
        assert memo is not None
        title = self.text.line("memo_title", sender=memo.sender)
        self.push_screen(MemoScreen(memo_lines(memo, self.text), title), self._to_the_desk)

    def _to_the_desk(self, _: None) -> None:
        assert self.checkin is not None
        self.push_screen(DeskScreen(self.checkin, self.text), self._left_the_desk)

    def _left_the_desk(self, choice: str | None) -> None:
        """Down the Shaft, saving first (the autosave); or Save & quit, which comes back to the
        desk if the save is declined or fails."""
        assert self.checkin is not None
        checkin = self.checkin
        carry = checkin.finish()
        run = SavedRun(
            self.game.spec.seed, self.class_id, self.start_rank, self.game.spec.level + 1, carry,
            None, [],
        )  # fmt: skip
        if choice == "save":

            def saved(ok: bool) -> None:
                if ok and self._write(run):
                    self.exit()
                else:
                    self.push_screen(DeskScreen(checkin, self.text), self._left_the_desk)

            self._may_save(saved)
            return
        if self.saves is not None and (self.owns_slot or not has_save(self.saves)):
            self._write(run, quiet=True)  # the autosave: never over a run that is not yours
        self._next_level(carry)

    # -- saving ----------------------------------------------------------------------------

    def _current_run(self) -> SavedRun:
        spec = self.game.spec
        return SavedRun(
            spec.seed, self.class_id, self.start_rank, spec.level, self.arrival, self.game,
            self.messages,
        )  # fmt: skip

    def _may_save(self, then: Callable[[bool], None]) -> None:
        """Call `then(True)` if the save slot may be written: there is nowhere to save (False),
        it is this run's or empty (True), or the player agrees to replace another run's."""
        if self.saves is None:
            then(False)
        elif self.owns_slot or not has_save(self.saves):
            then(True)
        else:
            prompt = self.text.line("menu_replace_prompt", folder=self.saves)
            keys = self.text.line("confirm_keys")
            self.push_screen(ConfirmScreen([prompt, "", keys]), lambda yes: then(bool(yes)))

    def _write(self, run: SavedRun, quiet: bool = False) -> bool:
        """Write the save; a failure is said (unless quiet), never swallowed."""
        assert self.saves is not None
        try:
            write_save(self.saves, run)
        except SaveError as err:
            if not quiet:
                self._say(self.text.line("save_failed", message=str(err)))
            return False
        self.owns_slot = True
        return True

    def _save_and_quit(self) -> None:
        def saved(ok: bool) -> None:
            if ok and self._write(self._current_run()):
                self.exit()

        self._may_save(saved)

    def _menu(self) -> None:
        lines = [self.text.line("menu_save"), self.text.line("menu_back")]
        self.push_screen(MenuScreen(lines, self.text.line("menu_title")), self._menu_chosen)

    def _menu_chosen(self, choice: str | None) -> None:
        if choice == "save":
            self._save_and_quit()

    def _next_level(self, carry: Carry) -> None:
        self.arrival = carry
        self._start_level(Seed(self.game.spec.seed), self.game.spec.level + 1)

    # -- input -----------------------------------------------------------------------------

    def on_key(self, event: Key) -> None:
        if self.game.dead or self.screen_stack[0].has_class("too-small"):
            return
        if self.pending is not None:
            confirmed, self.pending = self.pending, None  # any key answers; only y means yes
            if event.key == "y":
                confirmed()
            return
        action = lookup(event.key, event.character)
        if self.look_pos is not None:
            self._look_key(event.key, action)
        elif isinstance(action, UiAction):
            self._ui_action(action)
        elif isinstance(action, Move) and self._ask_about_move(action):
            return
        elif action is not None:
            self._play(action)

    def _ask(self, line: str, then: Callable[[], None]) -> None:
        self._say(line)
        self.pending = then

    def _ask_about_move(self, move: Move) -> bool:
        """Dangerous steps need a decision: onto a known trap, or into Brine with a lit torch."""
        view = self.game.view()
        dest = view.player.step((move.dx, move.dy))
        trap = next((t for t in view.traps if t.pos == dest and not t.disarmed), None)
        if trap is None:
            if view.torch_lit and self.game.grid.get(dest.x, dest.y) == Tile.BRINE:
                self._ask(self.text.line("brine_prompt"), lambda: self._play(move))
                return True
            return False
        if view.hero.signature == "backstab":
            self._ask(
                self.text.line("disarm_prompt", name=trap.name),
                lambda: self._play(Disarm(move.dx, move.dy)),
            )
        else:
            self._ask(self.text.line("step_prompt", name=trap.name), lambda: self._play(move))
        return True

    def _play(self, command: Command) -> None:
        reading: DocumentRead | None = None
        at_crate = False
        for event in self.game.submit(command):
            if line := describe(event, self.text, self.game.light_radius):
                self._say(line)
            if isinstance(event, DocumentRead):
                reading = event
            at_crate = at_crate or isinstance(event, AtCrate)
        self._sync()
        if self.game.dead:
            self._report_death()
        elif at_crate:
            self.push_screen(InvoiceScreen(self.game, self.text), self._invoice_done)
        elif reading is not None:
            keys = self.text.line("document_keys")
            self.push_screen(DocumentScreen(reading.text, self.text.line("document_title"), keys))

    def _invoice_done(self, picks: tuple[int, ...] | None) -> None:
        if picks:
            self._play(TakeSupply(picks))

    def _ui_action(self, action: UiAction) -> None:
        if action is UiAction.QUIT:
            self._ask(self.text.line("quit_prompt"), self.exit)
        elif action is UiAction.SHEET:
            lines = sheet_lines(self.game, self.text)
            self.push_screen(SheetScreen(lines, self.text.line("sheet_title")))
        elif action is UiAction.MENU:
            self._menu()
        elif action is UiAction.HELP:
            self.push_screen(HelpScreen(self.text.line("help_text"), self.text.line("help_title")))
        elif action is UiAction.DESCEND or action is UiAction.SKIP:
            self._descend(forced=action is UiAction.SKIP)
        elif action is UiAction.INVENTORY:
            lines = pack_lines(self.game.view(), self.text)
            self.push_screen(
                PackScreen(
                    lines,
                    self.text.line("inventory_title"),
                    self.text.line("inventory_keys"),
                    0,
                    False,
                )
            )
        elif action in (UiAction.EQUIP, UiAction.USE, UiAction.DROP):
            self._item_menu(action)
        elif action is UiAction.LOOK:
            self.look_pos = self.game.pos
        elif action is UiAction.GLYPHS:
            self.glyph_name = "ascii" if self.glyph_name == "unicode" else "unicode"
        elif action is UiAction.REDRAW:
            self.refresh(layout=True)
        self._sync()

    def _item_menu(self, action: UiAction) -> None:
        view = self.game.view()
        if not view.pack:
            self._say(self.text.line("inventory_empty"))
            return
        prompt = self.text.line(
            {UiAction.EQUIP: "menu_equip", UiAction.USE: "menu_use", UiAction.DROP: "menu_drop"}[
                action
            ]
        )
        screen = PackScreen(
            pack_lines(view, self.text),
            self.text.line("inventory_title"),
            prompt,
            len(view.pack),
            True,
        )
        self.push_screen(screen, lambda choice: self._item_chosen(action, choice))

    def _item_chosen(self, action: UiAction, choice: tuple[int, bool] | None) -> None:
        if choice is None:
            return
        slot, off_hand = choice
        if action is UiAction.EQUIP:
            self._play(Equip(slot, off_hand))
        elif action is UiAction.USE:
            self._play(UseItem(slot))
        else:
            self._play(DropItem(slot))

    def _look_key(self, key: str, action: Command | UiAction | None) -> None:
        assert self.look_pos is not None
        if key == "escape" or action is UiAction.LOOK:
            self.look_pos = None
        elif isinstance(action, Move):
            spec = self.game.spec
            self.look_pos = Pos(
                max(0, min(spec.width - 1, self.look_pos.x + action.dx)),
                max(0, min(spec.height - 1, self.look_pos.y + action.dy)),
            )
        elif action is UiAction.GLYPHS:
            self._ui_action(action)
        self._sync()

    # -- death -----------------------------------------------------------------------------

    def _report_death(self) -> None:
        """The Posthumous Pay Slip first (GDD 8.8), then the incident report."""
        self._show_slip()

    def _close_the_books(self, outcome: str) -> list[str]:
        """The run is over: file its record, and take down the save if it was this run's.
        Whatever goes wrong is reported on the screen, never swallowed."""
        if self.saves is None:
            return []
        trouble = []
        try:
            append_record(self.saves, make_record(self.game, outcome))
        except SaveError as err:
            trouble.append(self.text.line("record_failed", message=str(err)))
        if self.owns_slot:
            try:
                delete_save(self.saves)
            except SaveError as err:
                trouble.append(str(err))
        return ["", *trouble] if trouble else []

    def _score_lines(self) -> list[str]:
        score = self.game.score()
        title = self.text.line("title_" + title_key(score, self.game.economy))
        return [
            self.text.line("death_score", score=score),
            self.text.line("death_final_title", title=title),
        ]

    def _death_report(self) -> None:
        hero = self.game.view().hero
        spec = self.game.spec
        t = self.text
        lines = [
            t.line("death_associate", name=hero.name, class_name=hero.class_name, rank=hero.rank),
            t.line("death_cause", killer=hero.cause),
            t.line(
                "death_order",
                number=spec.level,
                total=LEVELS,
                work_order=t.levels[spec.level - 1].work_order,
            ),
            t.line("death_turns", turns=self.game.ticks // 100),
            t.line("death_seed", seed=Seed(spec.seed).share_code),
            *self._score_lines(),
            "",
            t.line("death_regret"),
            *self._close_the_books("death"),
            "",
            t.line("death_keys"),
        ]
        self.push_screen(DeathScreen(lines, t.line("death_title")), self._after_death)

    def _review(self) -> None:
        """Out of the Surface Lift: the performance review ends the run."""
        hero = self.game.view().hero
        t = self.text
        lines = [
            t.line("review_surface"),
            t.line("death_associate", name=hero.name, class_name=hero.class_name, rank=hero.rank),
            t.line("death_seed", seed=Seed(self.game.spec.seed).share_code),
            *self._score_lines(),
            *self._close_the_books("victory"),
            "",
            t.line("review_keys"),
        ]
        self.push_screen(ReviewScreen(lines, t.line("review_title")), self._after_review)

    def _after_review(self, choice: str | None) -> None:
        if choice == "new":
            self.arrival = None
            self.start_rank = self.game.player.rank
            self._start_level(Seed.parse(seed_text_from_entropy(secrets.token_bytes(8))), 1)
        else:
            self.exit()

    def _after_death(self, choice: str | None) -> None:
        if choice == "retry":
            self._restart(Seed(self.game.spec.seed))
        elif choice == "new":
            self._restart(Seed.parse(seed_text_from_entropy(secrets.token_bytes(8))))
        else:
            self.exit()

    # -- drawing ---------------------------------------------------------------------------

    def _say(self, line: str) -> None:
        self.messages = [*self.messages, line][-LOG_KEPT:]
        self._refresh_log()

    def _refresh_log(self) -> None:
        panel = self.query_one("#log", Static)
        shown = wrap_log(
            self.messages, panel.size.width or MIN_SIZE[0], log_lines(self.size.height)
        )
        panel.update(_plain("\n".join(shown)))

    def _sync(self) -> None:
        view = self.game.view()
        glyphs = glyph_set(self.glyph_name)
        map_view = self.query_one(MapView)
        overlays = {}
        for f in view.floor:
            style = ITEM_STYLES[f.glyph]
            seen_now = view.vis[f.pos.y * view.width + f.pos.x] == VISIBLE
            overlays[f.pos] = (glyphs.items[f.glyph], style if seen_now else dim(style))
        for c in view.crates:
            overlays[c.pos] = (glyphs.crate, CRATE)
        overlays |= {
            t.pos: (glyphs.trap_off, TRAP_OFF) if t.disarmed else (glyphs.trap, TRAP)
            for t in view.traps
        }
        for m in view.sensed:
            overlays[m.pos] = (glyphs.sensed or glyphs.monsters[m.kind], SENSED)
        for m in view.monsters:
            faction = self.game.data.monsters[m.kind].faction
            overlays[m.pos] = (glyphs.monsters[m.kind], FACTION_STYLES[faction])
        overlays[view.player] = PLAYER
        map_view.set_scene(
            self.game.grid, view.vis, overlays, glyphs, self.look_pos, view.graveyard
        )
        map_view.follow(self.look_pos or view.player)
        map_view.border_subtitle = self._look_text(view) if self.look_pos else ""
        share = Seed(view.seed).share_code
        self.query_one("#status", Static).update(
            _plain("\n".join(status_lines(view, glyphs, share)))
        )

    def _look_text(self, view: GameView) -> str:
        assert self.look_pos is not None
        for m in view.monsters:
            if m.pos == self.look_pos:
                return f"{m.name} {m.hp}/{m.max_hp}"
        if (here := next((f for f in view.floor if f.pos == self.look_pos), None)) is not None:
            return here.name
        state = view.vis[self.look_pos.y * view.width + self.look_pos.x]
        if state == UNSEEN:
            return self.text.line("look_unexplored")
        name = self.text.tile_name(self.game.grid.get(self.look_pos.x, self.look_pos.y))
        return self.text.line("look_remembered", name=name) if state == REMEMBERED else name


def run(
    seed: Seed,
    level: int,
    glyphs: str,
    rank: int = 1,
    class_id: str = "fighter",
    saves: Path | None = None,
    owns_slot: bool = False,
) -> None:
    game = Game.new(seed, level, rank, class_id)
    GameApp(game, glyphs, saves=saves, owns_slot=owns_slot).run()


def run_saved(saved: SavedRun, glyphs: str, saves: Path) -> None:
    """Carry on a saved run: the level in play, or the arrival on the next one."""
    game = saved.game
    if game is None:
        game = Game.new(
            Seed(saved.seed), saved.level, saved.start_rank, saved.class_id, carry=saved.arrival
        )
    GameApp(game, glyphs, saves=saves, resume=saved).run()


def selftest(seed: Seed, level: int, glyphs: str) -> str:
    """Start the game without a terminal; proves Textual, the theme file, and data all load."""

    async def go() -> str:
        app = GameApp(Game.new(seed, level), glyphs)
        async with app.run_test(size=MIN_SIZE) as pilot:
            await pilot.pause()
            name = app.text.levels[level - 1].name
            return f"ui ok: seed {seed.share_code}  Level {level}  {name}  glyphs {glyphs}"

    return asyncio.run(go())
