"""Read-only level viewer (`--view`): every tile revealed, pan and switch levels."""

from importlib import resources

from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Static

from minetoofar.content.balance import LEVELS
from minetoofar.core.seed import Seed
from minetoofar.gen.layout import generate_level
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.ui.glyphs import glyph_set
from minetoofar.ui.mapview import MapView

PAN_X, PAN_Y = 4, 2
PAN_KEYS = {
    "left": (-PAN_X, 0), "h": (-PAN_X, 0), "right": (PAN_X, 0), "l": (PAN_X, 0),
    "up": (0, -PAN_Y), "k": (0, -PAN_Y), "down": (0, PAN_Y), "j": (0, PAN_Y),
}  # fmt: skip


class MapApp(App[None]):
    CSS = resources.files("minetoofar.ui").joinpath("theme.tcss").read_text("utf-8")

    def __init__(self, seed: Seed, level: int, glyphs: str) -> None:
        super().__init__()
        self.seed = seed
        self.level = level
        self.glyph_name = glyphs

    def compose(self) -> ComposeResult:
        yield Static(id="header")
        yield MapView(self._spec(), glyph_set(self.glyph_name))
        yield Static("arrows/hjkl pan  [ ] level  F2 glyphs  q quit", id="footer")

    def on_mount(self) -> None:
        self._update_header()

    def _spec(self) -> LevelSpec:
        return generate_level(self.seed, self.level)

    def _update_header(self) -> None:
        spec = self.query_one(MapView).spec
        self.query_one("#header", Static).update(
            f"A Mine Too Far  seed {self.seed.share_code}  Level {self.level}  "
            f"rooms {len(spec.rooms)}  glyphs {self.glyph_name}"
        )

    def _reload(self) -> None:
        self.query_one(MapView).show(self._spec(), glyph_set(self.glyph_name))
        self._update_header()

    def on_key(self, event: Key) -> None:
        if event.key in PAN_KEYS:
            self.query_one(MapView).pan(*PAN_KEYS[event.key])
        elif event.key == "f2":
            self.glyph_name = "ascii" if self.glyph_name == "unicode" else "unicode"
            self._reload()
        elif event.key in ("left_square_bracket", "right_square_bracket"):
            step = 1 if event.key == "right_square_bracket" else -1
            self.level = max(1, min(LEVELS, self.level + step))
            self._reload()
        elif event.key == "q":
            self.exit()


def run_viewer(seed: Seed, level: int, glyphs: str) -> None:
    MapApp(seed, level, glyphs).run()
