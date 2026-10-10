"""The class select screen shown before a new run (milestone 4)."""

from importlib import resources

from rich.text import Text as RichText
from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Static

from minetoofar.content.gamedata import GameData, load_gamedata
from minetoofar.content.text import Text, load_text

DIGITS = {"1": 0, "2": 1, "3": 2}


class ClassSelectApp(App[str | None]):
    """Returns the chosen class id, or None when the player quits."""

    CSS = resources.files("minetoofar.ui").joinpath("theme.tcss").read_text("utf-8")

    def __init__(self) -> None:
        super().__init__()
        self.data: GameData = load_gamedata()
        self.text: Text = load_text()
        self.ids = list(self.data.classes)
        self.index = 0

    def compose(self) -> ComposeResult:
        panel = Static(id="select")
        panel.border_title = self.text.line("select_title")
        yield panel

    def on_mount(self) -> None:
        self._draw()

    def _draw(self) -> None:
        items = self.data.items
        lines: list[str] = []
        for i, class_id in enumerate(self.ids):
            c = self.data.classes[class_id]
            kit = [items.weapons[c.weapon].name]
            off = items.weapons.get(c.offhand) or items.shields.get(c.offhand)
            if off:
                kit.append(off.name)
            kit.append(items.armor[c.body].name)
            marker = ">" if i == self.index else " "
            lines += [
                f"{marker} {i + 1}  {c.name:<8} HP {c.rank_hp[0]:<3} "
                f"STR {c.strength}  DEX {c.dexterity}",
                f"       {', '.join(kit)}",
                f"       {c.blurb}",
                "",
            ]
        lines.append(self.text.line("select_keys"))
        self.query_one("#select", Static).update(RichText("\n".join(lines)))

    def on_key(self, event: Key) -> None:
        last = len(self.ids) - 1
        if event.key in DIGITS and DIGITS[event.key] <= last:
            self.index = DIGITS[event.key]
        elif event.key in ("down", "j"):
            self.index = min(last, self.index + 1)
        elif event.key in ("up", "k"):
            self.index = max(0, self.index - 1)
        elif event.key == "enter":
            self.exit(self.ids[self.index])
        elif event.key in ("q", "escape"):
            self.exit(None)
        self._draw()


def choose_class() -> str | None:
    return ClassSelectApp().run()
