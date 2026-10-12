"""Documents (GDD 8.3): read where they lie, for flavor, a coupon, or a map."""

from minetoofar.content.docs import load_docs
from minetoofar.core.seed import Seed
from minetoofar.gen.world import generate_world
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.events import DocumentRead, Pickup
from minetoofar.sim.game import UNSEEN, VISIBLE, Game
from tests.helpers import make_game

ROOM = ["#########", "#<......#", "#########"]
BOOK = load_docs()


def with_doc(kind: str, text: int = 0) -> Game:
    g = make_game(ROOM)
    g.floor.append(FloorItem(g.pos, Item(kind, text=text)))
    return g


def test_a_memo_is_read_on_the_spot_for_fifty_ticks() -> None:
    g = with_doc("memo", 2)
    assert g.submit(Pickup()) == [DocumentRead("memo", BOOK.text("memo", 2))]
    assert g.floor == [] and g.ticks == 50 and g.account.coupons == 0


def test_a_coupon_is_added_to_the_account() -> None:
    g = with_doc("coupon", 1)
    assert g.submit(Pickup()) == [DocumentRead("coupon", BOOK.text("coupon", 1))]
    assert g.account.coupons == 1


def test_a_second_coupon_is_a_second_coupon() -> None:
    g = with_doc("coupon")
    g.floor.append(FloorItem(g.pos, Item("coupon")))
    g.submit(Pickup())
    g.submit(Pickup())
    assert g.account.coupons == 2


def test_a_map_fragment_shows_every_room_without_lighting_it() -> None:
    g = Game.new(Seed.parse("GOLD0001"), 2)
    g.floor.append(FloorItem(g.pos, Item("map")))
    width = g.spec.width
    far = [r for r in g.spec.rooms if r.anchor != g.pos][-1]
    assert g.view().vis[far.anchor.y * width + far.anchor.x] == UNSEEN
    events = g.submit(Pickup())
    assert isinstance(events[0], DocumentRead) and events[0].kind == "map"
    vis = g.view().vis
    for room in g.spec.rooms:
        assert all(
            vis[y * width + x] != UNSEEN
            for y in range(room.y - 1, room.y + room.h + 1)
            for x in range(room.x - 1, room.x + room.w + 1)
            if g.grid.in_bounds(x, y)
        ), room.id
    assert vis[far.anchor.y * width + far.anchor.x] != VISIBLE  # remembered, not seen now


def test_a_generated_level_arrives_with_its_loot_and_drops() -> None:
    seed = Seed.parse("GOLD0005")
    world = generate_world(seed, 3)
    g = Game.new(seed, 3)
    assert [(f.pos, f.item.id) for f in g.floor] == [(p, i.id) for p, i in world.loot.items]
    assert sorted(g.drops) == sorted(mid for mid, _ in world.loot.drops)
    badger_ids = [i + 1 for i, s in enumerate(world.monsters.spawns) if s.kind == "gem_badger"]
    for mid in badger_ids:
        assert g.drops[mid][0].id == "rough_gem"
