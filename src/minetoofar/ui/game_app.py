"""The playable screen: map, status panel, log, look mode, prompts, the character sheet, the death
report, and the too-small guard."""

import asyncio
import secrets
from collections.abc import Callable
from importlib import resources

from rich.style import Style
from rich.text import Text as RichText
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key, Resize
from textual.screen import ModalScreen
from textual.widgets import Static

from minetoofar.content.balance import LEVELS
from minetoofar.content.text import Text, load_text
from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.core.seed import Seed, seed_text_from_entropy
from minetoofar.sim.events import Command, Disarm, Move
from minetoofar.sim.game import REMEMBERED, UNSEEN, Game, GameView
from minetoofar.ui.glyphs import glyph_set
from minetoofar.ui.keymap import UiAction, lookup
from minetoofar.ui.logtext import describe, wrap_log
from minetoofar.ui.mapview import MapView
from minetoofar.ui.panels import sheet_lines, status_lines

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
LOG_KEPT = 200


def log_lines(rows: int) -> int:
    """Log panel height (GDD 5.1): four lines on the minimum screen, up to ten on a tall one."""
    return max(4, min(10, rows // 6))


def _plain(text: str) -> RichText:
    """Panel text without markup parsing, clipped with an ellipsis instead of wrapping."""
    return RichText(text, no_wrap=True, overflow="ellipsis")


class DeathScreen(ModalScreen[str]):
    """The incident report: R retries the seed, N starts a new one, Q quits."""

    def __init__(self, lines: list[str], title: str) -> None:
        super().__init__()
        self._lines = lines
        self._title = title

    def compose(self) -> ComposeResult:
        report = Static(RichText("\n".join(self._lines)), id="death")
        report.border_title = self._title
        yield report

    def on_key(self, event: Key) -> None:
        choice = {"r": "retry", "n": "new", "q": "quit", "escape": "quit"}.get(event.key)
        event.stop()
        if choice:
            self.dismiss(choice)


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


class GameApp(App[None]):
    CSS = resources.files("minetoofar.ui").joinpath("theme.tcss").read_text("utf-8")

    def __init__(self, game: Game, glyphs: str) -> None:
        super().__init__()
        self.game = game
        self.glyph_name = glyphs
        self.text: Text = load_text()
        self.messages: list[str] = []
        self.look_pos: Pos | None = None
        self.pending: Callable[[], None] | None = None  # what a "y" answers, while a prompt is up
        self.start_rank = game.player.rank  # a retry begins where this level began
        self.start_armor = game.player.body_dur
        self.class_id = game.player.class_id

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
        self._say(
            self.text.line("welcome", number=spec.level, total=LEVELS, work_order=info.work_order)
        )
        self._sync()

    def _start_level(self, seed: Seed, level: int) -> None:
        self.game = Game.new(seed, level, self.start_rank, self.class_id, self.start_armor)
        self._begin()

    def _restart(self, seed: Seed) -> None:
        self._start_level(seed, self.game.spec.level)

    def _descend(self, forced: bool) -> None:
        """Take the Down Shaft (or, with `forced`, the debug skip) to the next level."""
        player, level = self.game.player, self.game.spec.level
        if not forced and self.game.grid.get(player.pos.x, player.pos.y) != Tile.EXIT:
            self._say(self.text.line("descend_none"))
        elif level >= LEVELS:
            self._say(self.text.line("descend_last"))
        else:
            self.start_rank, self.start_armor = player.rank, player.body_dur
            self._start_level(Seed(self.game.spec.seed), level + 1)

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
        for event in self.game.submit(command):
            if line := describe(event, self.text, self.game.light_radius):
                self._say(line)
        self._sync()
        if self.game.dead:
            self._report_death()

    def _ui_action(self, action: UiAction) -> None:
        if action is UiAction.QUIT:
            self._ask(self.text.line("quit_prompt"), self.exit)
        elif action is UiAction.SHEET:
            lines = sheet_lines(self.game, self.text)
            self.push_screen(SheetScreen(lines, self.text.line("sheet_title")))
        elif action is UiAction.DESCEND or action is UiAction.SKIP:
            self._descend(forced=action is UiAction.SKIP)
        elif action is UiAction.LOOK:
            self.look_pos = self.game.pos
        elif action is UiAction.GLYPHS:
            self.glyph_name = "ascii" if self.glyph_name == "unicode" else "unicode"
        elif action is UiAction.REDRAW:
            self.refresh(layout=True)
        self._sync()

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
            "",
            t.line("death_regret"),
            "",
            t.line("death_keys"),
        ]
        self.push_screen(DeathScreen(lines, t.line("death_title")), self._after_death)

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
        overlays = {
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
        state = view.vis[self.look_pos.y * view.width + self.look_pos.x]
        if state == UNSEEN:
            return self.text.line("look_unexplored")
        name = self.text.tile_name(self.game.grid.get(self.look_pos.x, self.look_pos.y))
        return self.text.line("look_remembered", name=name) if state == REMEMBERED else name


def run(seed: Seed, level: int, glyphs: str, rank: int = 1, class_id: str = "fighter") -> None:
    GameApp(Game.new(seed, level, rank, class_id), glyphs).run()


def selftest(seed: Seed, level: int, glyphs: str) -> str:
    """Start the game without a terminal; proves Textual, the theme file, and data all load."""

    async def go() -> str:
        app = GameApp(Game.new(seed, level), glyphs)
        async with app.run_test(size=MIN_SIZE) as pilot:
            await pilot.pause()
            name = app.text.levels[level - 1].name
            return f"ui ok: seed {seed.share_code}  Level {level}  {name}  glyphs {glyphs}"

    return asyncio.run(go())
