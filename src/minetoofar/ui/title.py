"""The title menu (M8): Continue a saved run, start a New run, read the employment history,
or Quit."""

from importlib import resources
from pathlib import Path

from rich.text import Text as RichText
from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Static

from minetoofar.content.balance import LEVELS
from minetoofar.content.gamedata import load_gamedata
from minetoofar.content.text import Text, load_text
from minetoofar.core.seed import Seed
from minetoofar.persist.errors import SaveError
from minetoofar.persist.records import read_records
from minetoofar.persist.save import SavedRun, delete_save, has_save, load_save
from minetoofar.ui.personnel import record_lines

Choice = tuple[str, SavedRun | None]


class TitleApp(App[Choice]):
    """Returns ("continue", the saved run), ("new", None) or ("quit", None)."""

    CSS = resources.files("minetoofar.ui").joinpath("theme.tcss").read_text("utf-8")

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self.folder = folder
        self.text: Text = load_text()
        self.saved: SavedRun | None = None
        self.problem = ""  # why a save that is there cannot be continued
        self.confirming = False
        self.history = False  # showing the employment history instead of the menu
        if has_save(folder):
            try:
                self.saved = load_save(folder)
            except SaveError as err:
                self.problem = str(err)

    def compose(self) -> ComposeResult:
        yield Static(id="title")

    def on_mount(self) -> None:
        self._draw()

    def _draw(self) -> None:
        t = self.text
        lines = [t.line("title_name"), t.line("title_tagline"), ""]
        if self.history:
            lines = self._history_lines()
        elif self.confirming:
            lines += [t.line("title_confirm_new")]
        else:
            if self.saved is not None:
                lines.append(self._continue_line(self.saved))
            lines += [t.line("title_new"), t.line("title_records"), t.line("title_quit")]
            if self.problem:
                lines += ["", self.problem]
        self.query_one("#title", Static).update(RichText("\n".join(lines)))

    def _history_lines(self) -> list[str]:
        try:
            return record_lines(read_records(self.folder), self.text)
        except SaveError as err:
            t = self.text
            return [t.line("records_title"), "", str(err), "", t.line("records_back")]

    def _continue_line(self, run: SavedRun) -> str:
        c = load_gamedata().classes[run.class_id]
        return self.text.line(
            "title_continue",
            class_name=c.name,
            number=run.level,
            total=LEVELS,
            seed=Seed(run.seed).share_code,
        )

    def on_key(self, event: Key) -> None:
        key = event.key
        if self.history:
            if key in ("escape", "q", "enter"):
                self.history = False
                self._draw()
        elif self.confirming:
            if key == "y":
                delete_save(self.folder)
                self.exit(("new", None))
            elif key in ("n", "escape"):
                self.confirming = False
                self._draw()
        elif key == "c" and self.saved is not None:
            self.exit(("continue", self.saved))
        elif key == "r":
            self.history = True
            self._draw()
        elif key == "n":
            if has_save(self.folder):
                self.confirming = True
                self._draw()
            else:
                self.exit(("new", None))
        elif key in ("q", "escape"):
            self.exit(("quit", None))


def choose_start(folder: Path) -> Choice:
    return TitleApp(folder).run() or ("quit", None)
