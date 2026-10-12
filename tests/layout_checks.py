"""Structural invariants every generated level must satisfy (shared by unit, golden, fuzz)."""

from minetoofar.content.balance import LEVELS, Balance
from minetoofar.content.desk import load_desk
from minetoofar.content.gamedata import GameData
from minetoofar.content.loot import DOCUMENTS, load_loot
from minetoofar.core.geometry import DIRS8, Pos
from minetoofar.core.grid import Grid, Tile, is_walkable
from minetoofar.core.pathing import distance_map
from minetoofar.gen.level_spec import LevelSpec, Room
from minetoofar.gen.rooms import flood_candidates
from minetoofar.gen.spawns import threat_spent
from minetoofar.gen.world import World


def _inside(pos: Pos, room: Room) -> bool:
    return room.x <= pos.x < room.x + room.w and room.y <= pos.y < room.y + room.h


def check_level(spec: LevelSpec, balance: Balance) -> None:
    p = balance.layout
    grid = Grid(spec.width, spec.height, spec.tiles)
    assert (spec.width, spec.height) == (p.width, p.height)
    assert p.rooms_min <= len(spec.rooms) <= p.rooms_max

    entries: list[Pos] = []
    exits: list[Pos] = []
    for y in range(spec.height):
        for x in range(spec.width):
            tile = grid.get(x, y)
            if tile == Tile.ENTRY:
                entries.append(Pos(x, y))
            if tile == Tile.EXIT:
                exits.append(Pos(x, y))
            if is_walkable(tile):
                assert 0 < x < spec.width - 1 and 0 < y < spec.height - 1, (
                    f"floor on border {x},{y}"
                )
                for dx, dy in DIRS8:
                    assert grid.get(x + dx, y + dy) != Tile.SOLID, f"unwalled floor at {x},{y}"
            if tile == Tile.DOOR:
                ns = is_walkable(grid.get(x, y - 1)) and is_walkable(grid.get(x, y + 1))
                ew = is_walkable(grid.get(x - 1, y)) and is_walkable(grid.get(x + 1, y))
                assert ns != ew, f"door at {x},{y} is not a doorway"
    assert entries == [spec.entry] and exits == [spec.exit]
    assert spec.entry != spec.exit

    dist = distance_map(grid, spec.entry)
    assert spec.exit in dist
    for room in spec.rooms:
        assert room.anchor in dist, f"room {room.id} unreachable"
        assert 1 <= room.x and room.x + room.w <= spec.width - 1
        assert 1 <= room.y and room.y + room.h <= spec.height - 1

    # GDD 10.4 step 6: exit room is the farthest by path distance; ties go to the lowest (y, x).
    expected = min(
        (r for r in spec.rooms if dist[r.anchor] == max(dist[q.anchor] for q in spec.rooms)),
        key=lambda r: (r.anchor.y, r.anchor.x),
    )
    assert _inside(spec.exit, expected)
    assert not _inside(spec.entry, expected)

    # GDD 9.3: every level needs a room that can hold a Flooded Gallery (Level 3 needs more).
    skip = {r.id for r in spec.rooms if _inside(spec.entry, r) or _inside(spec.exit, r)}
    wanted = balance.features.level3_flooded_min if spec.level == 3 else 1
    found = flood_candidates(grid, list(spec.rooms), skip, balance.features.flood_min_pct)
    assert len(found) >= wanted, f"only {len(found)} rooms can be flooded"


def check_world(world: World, balance: Balance, data: GameData) -> None:
    """Everything the later stages promise (GDD 9.3-9.7, 10.4), checked on one finished level."""
    spec = world.spec
    grid = Grid(spec.width, spec.height, spec.tiles)
    p, level = balance.spawns, spec.level
    entry = next(r for r in spec.rooms if _inside(spec.entry, r))
    exit_ = next(r for r in spec.rooms if _inside(spec.exit, r))
    dist = distance_map(grid, spec.entry)

    # the threat budget (9.4, 9.5): spent, but not so much that another monster would have fit
    budget = p.budget_base + p.budget_per_level * level
    if world.theme.graveyard:
        budget = budget * p.graveyard_budget_pct // 100
    spent = threat_spent(world.spawns, data)
    cheapest = min(
        m.threat for m in data.monsters.values() if m.weight > 0 and m.min_level <= level
    )
    assert spent <= budget and budget - spent < cheapest, f"spent {spent} of {budget}"
    assert any(data.monsters[s.kind].faction == "beast" for s in world.spawns.spawns), "no beast"
    assert all(data.monsters[s.kind].min_level <= level for s in world.spawns.spawns)

    # Flooded Galleries (9.3): the right number, each at least 30% Brine
    flooded = [r for r in spec.rooms if world.room_kinds[r.id] == "flooded"]
    wanted = (balance.features.level3_flooded_min, balance.features.level3_flooded_max)
    assert (wanted[0] <= len(flooded) <= wanted[1]) if level == 3 else len(flooded) == 1
    for room in flooded:
        cells = [
            grid.get(x, y)
            for y in range(room.y, room.y + room.h)
            for x in range(room.x, room.x + room.w)
            if grid.get(x, y) in (Tile.FLOOR, Tile.CAVE_FLOOR, Tile.BRINE)
        ]
        assert cells.count(Tile.BRINE) * 100 >= balance.features.flood_min_pct * len(cells)

    # the Rogue Human (9.6): in an ordinary, reachable room
    h = world.humans
    assert h.room_id not in (entry.id, exit_.id)
    assert world.room_kinds[h.room_id] == h.room_kind
    assert h.pos in dist and grid.get(h.pos.x, h.pos.y) in (Tile.FLOOR, Tile.CAVE_FLOOR)
    assert _inside(h.pos, spec.rooms[h.room_id])

    # every monster stands where its kind belongs, alone, away from the entry (9.5)
    taken = {h.pos}
    per_room = {h.room_id: 1}
    for s in world.spawns.spawns:
        tile = grid.get(s.pos.x, s.pos.y)
        kind = data.monsters[s.kind]
        if kind.behavior == "eel":
            assert tile == Tile.BRINE and s.state == "submerged"
        elif s.state == "buried":
            assert tile == Tile.OPEN_GRAVE and s.kind == "shambling_miner" and world.theme.graveyard
        else:
            assert tile in (Tile.FLOOR, Tile.CAVE_FLOOR) and s.state in ("asleep", "idle")
        assert s.pos not in taken, f"two actors on {s.pos}"
        taken.add(s.pos)
        room = next(r for r in spec.rooms if _inside(s.pos, r))
        assert room.id not in (entry.id, exit_.id), f"{s.kind} in the entry or exit room"
        per_room[room.id] = per_room.get(room.id, 0) + 1
        assert dist[s.pos] >= p.min_entry_distance, f"{s.kind} too close to the entry"
    assert max(per_room.values()) <= p.room_cap

    # traps (9.7): on plain floor, alone, never in the entry room
    laid = [pos for pos, _ in world.traps.traps]
    assert len(set(laid)) == len(laid)
    for pos in laid:
        assert grid.get(pos.x, pos.y) in (Tile.FLOOR, Tile.CAVE_FLOOR)
        assert not _inside(pos, entry)
    camp = balance.humans.camp_traps if world.humans.room_kind == "prospector_camp" else 0
    assert len(laid) <= balance.trap_counts[level - 1] + camp  # fewer when no safe spot is left

    # graveyard props appear only on graveyard floors, and nothing cuts the level in two
    props = (Tile.GRAVESTONE, Tile.MONUMENT, Tile.OPEN_GRAVE)
    on_map = [
        Pos(x, y) for y in range(spec.height) for x in range(spec.width) if grid.get(x, y) in props
    ]
    assert world.theme.graveyard or not on_map
    bare = Grid(world.layout.width, world.layout.height, world.layout.tiles)
    reachable_before = set(distance_map(bare, spec.entry))
    blocked = {q for q in on_map if grid.get(q.x, q.y) in (Tile.GRAVESTONE, Tile.MONUMENT)}
    assert set(dist) == reachable_before - blocked

    # traps (9.7): none is the only way on, since only a Rogue can disarm one
    walls = [p for p, _ in world.traps.traps]
    assert grid.count_reachable(spec.entry, walls) == grid.count_reachable(spec.entry) - len(walls)

    # the loot (8.3, 8.4): the right number, on bare floor, one to a tile, and the lair's document
    loot = world.loot
    tables = load_loot()
    vaults = world.room_kinds.count("mausoleum")
    wanted = tables.base_items + tables.per_level_items * level + tables.extra_per_vault * vaults
    assert len(loot.items) == wanted + tables.lair_documents
    seen: set[Pos] = set()
    docs = 0
    in_lair = 0
    for pos, item in loot.items:
        assert grid.get(pos.x, pos.y) in (Tile.FLOOR, Tile.CAVE_FLOOR), f"loot on {pos}"
        assert pos not in seen and pos not in taken and pos not in (spec.entry, spec.exit)
        seen.add(pos)
        room = next(r for r in spec.rooms if _inside(pos, r))
        assert room.id not in (entry.id, exit_.id), "loot in the entry or exit room"
        if item.id in DOCUMENTS:
            docs += 1
            in_lair += room.id == h.room_id
        else:
            assert (
                item.id in data.items.valuables
                or item.id in data.items.consumables
                or (data.items.category(item.id) in ("weapon", "armor", "shield", "hat", "trinket"))
            )
    assert docs <= tables.document_cap + tables.lair_documents and in_lair >= tables.lair_documents
    ids = {i + 1: s.kind for i, s in enumerate(world.monsters.spawns)}
    assert {mid for mid, _ in loot.drops} == {m for m, k in ids.items() if k in tables.drops}

    # supply drops (8.5): inside the window, far enough apart, three distinct stock lines each
    sp = balance.supply
    drops = world.drops.drops
    assert len(drops) <= 2 and all(sp.trigger_min <= d.trigger <= sp.trigger_max for d in drops)
    if len(drops) == 2:
        assert drops[1].trigger - drops[0].trigger >= sp.second_gap
    for d in drops:
        stock = [ln.item for ln in d.lines if ln.item in data.items.consumables]
        assert len(stock) == sp.lines and len(set(stock)) == sp.lines
        assert len(d.lines) - len(stock) <= 1

    # the desk (5.3, 8.5): no desk after the last level, otherwise a bundle then distinct others
    desk = world.desk
    if level == LEVELS:
        assert desk.stock == () and desk.memo is None
    else:
        catalog = load_desk()
        assert len(desk.stock) == balance.checkin.desk_slots == len(set(desk.stock))
        assert catalog[desk.stock[0]].effect == "bundle"
        assert all(catalog[k].effect != "bundle" for k in desk.stock[1:])
        assert desk.memo is not None and f"Level {level + 1}" in "\n".join(desk.memo.lines)
