"""BSP rooms-and-corridors layout (GDD 10.4 steps 2-6). Integers only; one stream per attempt."""

from collections.abc import Iterator
from dataclasses import dataclass

from minetoofar.content.balance import LEVELS, Balance, LayoutParams, load_balance
from minetoofar.core.geometry import DIRS8, Pos
from minetoofar.core.grid import Grid, Tile, is_walkable
from minetoofar.core.pathing import distance_map
from minetoofar.core.rng import Rng
from minetoofar.core.seed import Seed
from minetoofar.gen.level_spec import LevelSpec, Room
from minetoofar.gen.rooms import flood_candidates


class GenerationError(RuntimeError):
    pass


@dataclass
class _Node:
    x: int
    y: int
    w: int
    h: int
    left: "_Node | None" = None
    right: "_Node | None" = None
    room: int = -1  # index into the room list, for leaves


def generate_level(seed: Seed, level: int, balance: Balance | None = None) -> LevelSpec:
    """Pure function of (seed, level): the level never depends on other levels or on play."""
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1-{LEVELS}, got {level}")
    bal = balance or load_balance()
    root = seed.rng()
    for attempt in range(bal.layout.max_attempts):
        rng = root.derive("level", level, "layout", attempt)
        spec = _try_layout(rng, seed.canonical, level, attempt, bal)
        if spec is not None:
            return spec
    raise GenerationError(
        f"no valid layout for seed {seed.canonical} level {level} in "
        f"{bal.layout.max_attempts} attempts"
    )


def _try_layout(rng: Rng, seed: str, level: int, attempt: int, bal: Balance) -> LevelSpec | None:
    p = bal.layout
    grid = Grid(p.width, p.height)
    tree = _Node(1, 1, p.width - 2, p.height - 2)
    _split(tree, 0, rng, p)

    rooms: list[Room] = []
    cells: list[list[Pos]] = []
    for leaf in _leaves(tree):
        leaf.room = len(rooms)
        room, room_cells = _make_room(rng, p, leaf, len(rooms), bal.cavern_pct[level - 1])
        for c in room_cells:
            grid.set(c.x, c.y, Tile.CAVE_FLOOR if room.cave else Tile.FLOOR)
        rooms.append(room)
        cells.append(room_cells)
    if not p.rooms_min <= len(rooms) <= p.rooms_max:
        return None

    links: set[tuple[int, int]] = set()
    _connect(tree, rooms, grid, rng, links)
    for _ in range(p.extra_links_base + level // p.extra_links_level_div):
        _extra_link(rooms, grid, rng, links)
    _place_doors(rooms, grid, rng, p)
    _build_walls(grid)

    entry_room = rooms[rng.below(len(rooms))]
    entry = cells[entry_room.id][0]  # cells are sorted (y, x): the room's top-left floor tile
    dist = distance_map(grid, entry)
    if any(r.anchor not in dist for r in rooms):
        return None
    farthest = max(dist[r.anchor] for r in rooms)
    exit_room = min(
        (r for r in rooms if dist[r.anchor] == farthest), key=lambda r: (r.anchor.y, r.anchor.x)
    )
    if exit_room is entry_room:
        return None
    # Every level needs room for a Flooded Gallery (Level 3 for several), GDD 9.3.
    needed = bal.features.level3_flooded_min if level == 3 else 1
    skip = {entry_room.id, exit_room.id}
    if len(flood_candidates(grid, rooms, skip, bal.features.flood_min_pct)) < needed:
        return None
    exit_ = cells[exit_room.id][0]
    grid.set(entry.x, entry.y, Tile.ENTRY)
    grid.set(exit_.x, exit_.y, Tile.EXIT)
    return LevelSpec(
        seed, level, p.width, p.height, grid.to_bytes(), tuple(rooms), entry, exit_, attempt
    )


def _split(node: _Node, depth: int, rng: Rng, p: LayoutParams) -> None:
    can_x, can_y = node.w >= 2 * p.leaf_min_w, node.h >= 2 * p.leaf_min_h
    if depth >= p.max_depth or not (can_x or can_y):
        return
    if depth >= p.early_stop_from_depth and rng.chance(p.early_stop_pct, 100):
        return
    if can_x and can_y:
        # Terminal cells are about twice as tall as wide, so compare the width with 2*height.
        if node.w == 2 * node.h:
            along_x = rng.chance(1, 2)
        else:
            long_axis_is_x = node.w > 2 * node.h
            along_x = rng.chance(p.split_long_axis_pct, 100) == long_axis_is_x
    else:
        along_x = can_x
    if along_x:
        off = rng.randrange(p.leaf_min_w, node.w - p.leaf_min_w + 1)
        node.left = _Node(node.x, node.y, off, node.h)
        node.right = _Node(node.x + off, node.y, node.w - off, node.h)
    else:
        off = rng.randrange(p.leaf_min_h, node.h - p.leaf_min_h + 1)
        node.left = _Node(node.x, node.y, node.w, off)
        node.right = _Node(node.x, node.y + off, node.w, node.h - off)
    _split(node.left, depth + 1, rng, p)
    _split(node.right, depth + 1, rng, p)


def _leaves(node: _Node) -> Iterator[_Node]:
    if node.left is None or node.right is None:
        yield node
    else:
        yield from _leaves(node.left)
        yield from _leaves(node.right)


def _make_room(
    rng: Rng, p: LayoutParams, leaf: _Node, room_id: int, cave_pct: int
) -> tuple[Room, list[Pos]]:
    m = p.room_margin
    w = rng.randrange(p.room_min, min(leaf.w - 2 * m, p.room_max_w) + 1)
    h = rng.randrange(p.room_min, min(leaf.h - 2 * m, p.room_max_h) + 1)
    x = leaf.x + m + rng.randrange(0, leaf.w - 2 * m - w + 1)
    y = leaf.y + m + rng.randrange(0, leaf.h - 2 * m - h + 1)
    cave_cells = None
    if rng.chance(cave_pct, 100):
        for _ in range(p.cave_tries):
            cave_cells = _cave_cells(rng, p, x, y, w, h)
            if cave_cells is not None:
                break
    center = Pos(x + w // 2, y + h // 2)
    if cave_cells is None:
        cells = [Pos(x + dx, y + dy) for dy in range(h) for dx in range(w)]
        anchor = center
    else:
        cells = cave_cells
        anchor = min(cells, key=lambda c: ((c.x - center.x) ** 2 + (c.y - center.y) ** 2, c.y, c.x))
    return Room(room_id, x, y, w, h, cave_cells is not None, anchor), cells


def _cave_cells(rng: Rng, p: LayoutParams, x0: int, y0: int, w: int, h: int) -> list[Pos] | None:
    """Cellular-automata blob; largest 4-connected floor region, or None if it is too small."""
    wall = [[rng.below(100) < p.cave_fill_pct for _ in range(w)] for _ in range(h)]
    for _ in range(p.cave_iterations):
        wall = [
            [_wall_count(wall, x, y, w, h) >= p.cave_wall_neighbors for x in range(w)]
            for y in range(h)
        ]
    seen = [[False] * w for _ in range(h)]
    best: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if wall[y][x] or seen[y][x]:
                continue
            region, stack = [], [(x, y)]
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                region.append((cx, cy))
                for nx, ny in ((cx, cy - 1), (cx + 1, cy), (cx, cy + 1), (cx - 1, cy)):
                    if 0 <= nx < w and 0 <= ny < h and not wall[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if len(region) > len(best):  # strict: ties keep the region found first (lowest y, x)
                best = region
    if len(best) * 100 < p.cave_min_pct * w * h:
        return None
    return sorted((Pos(x0 + x, y0 + y) for x, y in best), key=lambda c: (c.y, c.x))


def _wall_count(wall: list[list[bool]], x: int, y: int, w: int, h: int) -> int:
    count = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h) or wall[ny][nx]:
                count += 1
    return count


def _connect(
    node: _Node, rooms: list[Room], grid: Grid, rng: Rng, links: set[tuple[int, int]]
) -> list[Room]:
    if node.left is None or node.right is None:
        return [rooms[node.room]]
    left = _connect(node.left, rooms, grid, rng, links)
    right = _connect(node.right, rooms, grid, rng, links)
    a, b = min(
        ((a, b) for a in left for b in right),
        key=lambda ab: (_manhattan(ab[0].anchor, ab[1].anchor), ab[0].id, ab[1].id),
    )
    _carve_l(grid, a.anchor, b.anchor, rng.chance(1, 2))
    links.add((min(a.id, b.id), max(a.id, b.id)))
    return left + right


def _extra_link(rooms: list[Room], grid: Grid, rng: Rng, links: set[tuple[int, int]]) -> None:
    a = rooms[rng.below(len(rooms))]
    candidates = [
        b for b in rooms if b.id != a.id and (min(a.id, b.id), max(a.id, b.id)) not in links
    ]
    if not candidates:
        return
    b = min(candidates, key=lambda r: (_manhattan(a.anchor, r.anchor), r.id))
    _carve_l(grid, a.anchor, b.anchor, rng.chance(1, 2))
    links.add((min(a.id, b.id), max(a.id, b.id)))


def _manhattan(a: Pos, b: Pos) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _carve_l(grid: Grid, a: Pos, b: Pos, horizontal_first: bool) -> None:
    corner = Pos(b.x, a.y) if horizontal_first else Pos(a.x, b.y)
    for start, end in ((a, corner), (corner, b)):
        dx = (end.x > start.x) - (end.x < start.x)
        dy = (end.y > start.y) - (end.y < start.y)
        pos = start
        while True:
            if grid.get(pos.x, pos.y) == Tile.SOLID:
                grid.set(pos.x, pos.y, Tile.FLOOR)
            if pos == end:
                break
            pos = Pos(pos.x + dx, pos.y + dy)


def _place_doors(rooms: list[Room], grid: Grid, rng: Rng, p: LayoutParams) -> None:
    for r in rooms:
        if r.cave:
            continue
        ring = (
            [Pos(x, r.y - 1) for x in range(r.x, r.x + r.w)]
            + [Pos(x, r.y + r.h) for x in range(r.x, r.x + r.w)]
            + [Pos(r.x - 1, y) for y in range(r.y, r.y + r.h)]
            + [Pos(r.x + r.w, y) for y in range(r.y, r.y + r.h)]
        )
        for pos in ring:
            if grid.get(pos.x, pos.y) == Tile.FLOOR and _is_doorway(grid, pos):
                if rng.chance(p.door_pct, 100):
                    grid.set(pos.x, pos.y, Tile.DOOR)


def _is_doorway(grid: Grid, pos: Pos) -> bool:
    def open_(dx: int, dy: int) -> bool:
        return is_walkable(grid.get(pos.x + dx, pos.y + dy))

    ns, ew = open_(0, -1) and open_(0, 1), open_(-1, 0) and open_(1, 0)
    return ns != ew


def _build_walls(grid: Grid) -> None:
    """Ring every walkable tile with WALL, or ROCK where it touches cavern floor."""
    for y in range(grid.height):
        for x in range(grid.width):
            if grid.get(x, y) != Tile.SOLID:
                continue
            near = [grid.get(x + dx, y + dy) for dx, dy in DIRS8 if grid.in_bounds(x + dx, y + dy)]
            if any(is_walkable(t) for t in near):
                grid.set(x, y, Tile.ROCK if Tile.CAVE_FLOOR in near else Tile.WALL)
