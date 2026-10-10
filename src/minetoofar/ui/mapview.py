"""Scrolling map viewport: fog of war, overlays, and the look cursor."""

from collections.abc import Mapping

from rich.color import Color
from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widget import Widget

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Grid, Tile
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.sim.game import UNSEEN, VISIBLE
from minetoofar.ui.camera import follow_axis
from minetoofar.ui.glyphs import GlyphSet, render_cells

STYLES: dict[Tile, Style] = {
    Tile.SOLID: Style(),
    Tile.WALL: Style(color="#b8935a"),
    Tile.ROCK: Style(color="#6b6b6b"),
    Tile.FLOOR: Style(color="#7a6a55"),
    Tile.CAVE_FLOOR: Style(color="#707070"),
    Tile.DOOR: Style(color="#e0902a", bold=True),
    Tile.DOOR_OPEN: Style(color="#b5782a"),
    Tile.ENTRY: Style(color="#5fd35f", bold=True),
    Tile.EXIT: Style(color="#ffd34a", bold=True),
    Tile.BRINE: Style(color="#4a8fc0"),
    Tile.RUBBLE: Style(color="#8a7a65"),
    Tile.GRAVESTONE: Style(color="#a0a0a8"),
    Tile.MONUMENT: Style(color="#b0b0b8", bold=True),
    Tile.OPEN_GRAVE: Style(color="#6a5a50"),
}
# Graveyard floors swap only the floor and wall tints (GDD 5.4): dark green and grey-violet.
GRAVEYARD_STYLES: dict[Tile, Style] = STYLES | {
    Tile.FLOOR: Style(color="#3f6b45"),
    Tile.CAVE_FLOOR: Style(color="#3a5f40"),
    Tile.WALL: Style(color="#8a82a8"),
    Tile.ROCK: Style(color="#5f5a78"),
}
Overlay = tuple[str, Style]
DIM_PERCENT = 45  # remembered tiles keep their hue at this fraction of the brightness


def _dim(style: Style) -> Style:
    """A darker copy for remembered tiles; real colors, not the terminal's dim attribute."""
    if style.color is None:
        return style
    rgb = style.color.get_truecolor()
    r, g, b = (c * DIM_PERCENT // 100 for c in rgb)
    return Style(color=Color.from_rgb(r, g, b))


DIM_STYLES: dict[Tile, Style] = {tile: _dim(style) for tile, style in STYLES.items()}
GRAVEYARD_DIM_STYLES: dict[Tile, Style] = {t: _dim(s) for t, s in GRAVEYARD_STYLES.items()}
CURSOR = Style(reverse=True)


class MapView(Widget):
    """Draws a Grid through a camera. With no `vis` mask every tile is shown (the level viewer)."""

    def __init__(self, spec: LevelSpec, glyphs: GlyphSet, id: str | None = None) -> None:
        super().__init__(id=id)
        self.cam_x = 0
        self.cam_y = 0
        self.follows_focus = False  # the game keeps its focus on screen; the viewer pans freely
        self.focus_pos = spec.entry
        self._centered = False
        self.show(spec, glyphs)

    def show(self, spec: LevelSpec, glyphs: GlyphSet) -> None:
        """Display a fresh level with everything revealed."""
        self.spec = spec
        self.glyphs = glyphs
        self.grid = Grid(spec.width, spec.height, spec.tiles)
        self.vis: bytes | None = None
        self.graveyard = False
        self.overlays: Mapping[Pos, Overlay] = {}
        self.cursor: Pos | None = None
        self.focus_pos = spec.entry
        if self.size.width:
            self.center_on(spec.entry)
        else:
            self._centered = False
        self.refresh()

    def set_scene(
        self,
        grid: Grid,
        vis: bytes,
        overlays: Mapping[Pos, Overlay],
        glyphs: GlyphSet,
        cursor: Pos | None = None,
        graveyard: bool = False,
    ) -> None:
        self.grid, self.vis, self.overlays, self.glyphs, self.cursor, self.graveyard = (
            grid, vis, overlays, glyphs, cursor, graveyard,
        )  # fmt: skip
        self.refresh()

    def center_on(self, pos: Pos) -> None:
        self.focus_pos = pos
        self.cam_x = pos.x - self.size.width // 2
        self.cam_y = pos.y - self.size.height // 2
        self._centered = True
        self._clamp()
        self.refresh()

    def follow(self, pos: Pos) -> None:
        """Scroll just enough to keep `pos` inside the middle third of the view."""
        self.focus_pos = pos
        if not self.size.width or not self.size.height:
            return  # not laid out yet; the first resize centres on focus_pos
        self.cam_x = follow_axis(self.cam_x, pos.x, self.size.width, self.spec.width)
        self.cam_y = follow_axis(self.cam_y, pos.y, self.size.height, self.spec.height)
        self.refresh()

    def _clamp(self) -> None:
        self.cam_x = max(0, min(self.cam_x, self.spec.width - self.size.width))
        self.cam_y = max(0, min(self.cam_y, self.spec.height - self.size.height))

    def on_resize(self) -> None:
        if not self._centered:
            self.center_on(self.focus_pos)
        elif self.follows_focus:
            self.follow(self.focus_pos)
        else:
            self._clamp()
            self.refresh()

    def pan(self, dx: int, dy: int) -> None:
        self.cam_x += dx
        self.cam_y += dy
        self._clamp()
        self.refresh()

    def row_cells(self, y: int) -> list[tuple[str, Style]]:
        ly = y + self.cam_y
        if not 0 <= ly < self.spec.height:
            return []
        width = self.spec.width
        cells = render_cells(self.grid, ly, self.glyphs, self.vis)
        bright, dim = (
            (GRAVEYARD_STYLES, GRAVEYARD_DIM_STYLES) if self.graveyard else (STYLES, DIM_STYLES)
        )
        row: list[tuple[str, Style]] = []
        for x in range(self.cam_x, min(self.cam_x + self.size.width, width)):
            ch, tile = cells[x]
            state = VISIBLE if self.vis is None else self.vis[ly * width + x]
            if state == UNSEEN:
                ch, style = " ", Style()
            else:
                style = bright[tile] if state == VISIBLE else dim[tile]
            if (pos := Pos(x, ly)) in self.overlays:
                ch, style = self.overlays[pos]
            if pos == self.cursor:
                style = style + CURSOR
            row.append((ch, style))
        return row

    def row_text(self, y: int) -> str:
        return "".join(ch for ch, _ in self.row_cells(y)).ljust(self.size.width)

    def render_line(self, y: int) -> Strip:
        segments: list[Segment] = []
        for ch, style in self.row_cells(y):
            if segments and segments[-1].style == style:
                segments[-1] = Segment(segments[-1].text + ch, style)
            else:
                segments.append(Segment(ch, style))
        return Strip(segments).adjust_cell_length(self.size.width)
