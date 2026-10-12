"""The careful policy (the balance simulator's stand-in for competent play): what it does that
the reckless bot does not. The reckless bot's own behaviour is pinned by the replay logs."""

from minetoofar.core.geometry import Pos
from minetoofar.sim.actors import FloorItem, Item
from minetoofar.sim.bot import (
    CAREFUL,
    RECKLESS,
    Memory,
    Wait,
    _nearest_find,
    _sleepers_reach,
    choose,
)
from minetoofar.sim.events import DropItem, Move, Pickup, UseItem
from minetoofar.sim.items import KIT
from tests.helpers import MINER, inert, make_game

HALL = ["#" * 14, "#<.........>#", "#" * 14]
GRIMSBY = "foreman_grimsby"


def hall_with(*extra: tuple[str, tuple[int, int], str], **kw) -> object:  # type: ignore[no-untyped-def]
    return make_game(HALL, list(extra), **kw)


# -- waiting for a hunter ------------------------------------------------------------------------


def test_it_gives_up_waiting_for_a_hunter_that_never_comes() -> None:
    game = inert(make_game(HALL, [(MINER, (4, 1), "hunting")]))
    memory = Memory()
    sent = []
    for _ in range(40):
        command = choose(game, CAREFUL, memory)
        assert command is not None
        sent.append(command)
        game.submit(command)
        if not game.monsters:
            break
    assert not game.monsters, "it never went to fight the hunter"
    assert any(isinstance(c, Wait) for c in sent), "it should have waited first"


def test_the_reckless_bot_never_waits() -> None:
    game = inert(make_game(HALL, [(MINER, (4, 1), "hunting")]))
    assert not isinstance(choose(game, RECKLESS), Wait)


# -- finds beside sleepers -----------------------------------------------------------------------


def test_it_does_not_walk_up_to_a_find_beside_a_sleeper() -> None:
    nugget = [FloorItem(Pos(6, 1), Item("silver_nugget"))]
    game = make_game(HALL, [(MINER, (7, 1), "asleep")], floor=nugget)
    assert _nearest_find(game, CAREFUL, Memory()) is None
    assert _nearest_find(game, RECKLESS) == Pos(6, 1)


def test_it_takes_a_find_that_is_clear_of_the_sleepers() -> None:
    nugget = [FloorItem(Pos(3, 1), Item("silver_nugget"))]
    game = make_game(HALL, [(MINER, (9, 1), "asleep")], floor=nugget)
    assert _nearest_find(game, CAREFUL, Memory()) == Pos(3, 1)


def test_a_find_it_cannot_reach_without_waking_anyone_is_given_up_for_good() -> None:
    corridor = ["#" * 14, "#<.........>#", "#" * 14]
    nugget = [FloorItem(Pos(8, 1), Item("silver_nugget"))]
    game = make_game(corridor, [(MINER, (6, 1), "asleep")], floor=nugget)
    memory = Memory()
    assert choose(game, CAREFUL, memory) is not None
    assert Pos(8, 1) in memory.skip
    assert _nearest_find(game, CAREFUL, memory) is None


# -- a Rogue Human's sight -----------------------------------------------------------------------


def test_a_bosss_reach_is_what_he_can_see_not_a_square_round_him() -> None:
    rows = ["#" * 14, "#<...+......>#"[:14].ljust(14, "#"), "#" * 14]
    game = make_game(rows, [(GRIMSBY, (9, 1), "idle")])
    seen = _sleepers_reach(game, bosses_only=True)
    assert Pos(7, 1) in seen
    assert Pos(2, 1) not in seen, "the closed door is between them"


def test_bosses_only_leaves_the_small_fry_out() -> None:
    game = make_game(HALL, [(MINER, (5, 1), "asleep")])
    assert Pos(4, 1) in _sleepers_reach(game)
    assert _sleepers_reach(game, bosses_only=True) == set()


# -- preparing for the fight ---------------------------------------------------------------------


def test_it_drinks_overtime_fizz_when_a_human_is_coming() -> None:
    pack = [Item("overtime_fizz", 1, 4)]
    game = make_game(HALL, [(GRIMSBY, (6, 1), "hunting")], pack=pack)
    assert choose(game, CAREFUL, Memory()) == UseItem(0)
    assert not isinstance(choose(game, RECKLESS), UseItem)


def test_it_drinks_it_only_once() -> None:
    game = inert(
        make_game(HALL, [(GRIMSBY, (6, 1), "hunting")], pack=[Item("overtime_fizz", 2, 4)])
    )
    memory = Memory()
    game.submit(choose(game, CAREFUL, memory))  # type: ignore[arg-type]
    assert not isinstance(choose(game, CAREFUL, memory), UseItem)


def test_it_keeps_the_fizz_for_a_human_not_for_a_miner() -> None:
    game = make_game(HALL, [(MINER, (5, 1), "hunting")], pack=[Item("overtime_fizz", 1, 4)])
    assert not isinstance(choose(game, CAREFUL, Memory()), UseItem)


def test_it_coats_its_weapon_against_the_undead_that_are_coming() -> None:
    pack = [Item("sanctified_detergent", 1, 3)]
    game = make_game(HALL, [("gravedigger_skeleton", (6, 1), "hunting")], pack=pack, level=2)
    assert choose(game, CAREFUL, Memory()) == UseItem(0)


def test_it_tops_up_its_health_before_meeting_a_boss() -> None:
    game = make_game(HALL, [(GRIMSBY, (9, 1), "idle")], pack=[Item(KIT, 1, 5)])
    game.player.hp = game.player.max_hp - 12  # well above half, so the ordinary rule stays quiet
    assert choose(game, CAREFUL, Memory()) == UseItem(0)


def test_it_does_not_waste_a_kit_when_the_boss_is_far_off() -> None:
    wide = ["#" * 40, "#<" + "." * 36 + ">#", "#" * 40]
    game = make_game(wide, [(GRIMSBY, (35, 1), "idle")], pack=[Item(KIT, 1, 5)])
    game.player.hp = game.player.max_hp - 12
    assert not isinstance(choose(game, CAREFUL, Memory()), UseItem)


def test_it_walks_when_there_is_nothing_to_do_but_leave() -> None:
    game = make_game(HALL)
    assert isinstance(choose(game, CAREFUL, Memory()), Move)


# -- what is worth carrying ----------------------------------------------------------------------


def test_it_leaves_gear_that_is_no_better_than_what_it_wears() -> None:
    vest = [FloorItem(Pos(4, 1), Item("hi_vis_vest", 1, 0, 10))]  # the Fighter wears a boiler suit
    game = make_game(HALL, floor=vest)
    assert _nearest_find(game, CAREFUL, Memory()) is None
    assert _nearest_find(game, RECKLESS) == Pos(4, 1)


def test_it_takes_gear_that_is_better_than_what_it_wears() -> None:
    plate = [FloorItem(Pos(4, 1), Item("miners_plate", 1, 0, 20))]
    game = make_game(HALL, floor=plate)
    assert _nearest_find(game, CAREFUL, Memory()) == Pos(4, 1)


def test_it_drops_the_gear_it_has_swapped_out() -> None:
    game = make_game(HALL, pack=[Item("torch", 1, 1), Item("hi_vis_vest", 1, 0, 10)])
    assert choose(game, CAREFUL, Memory()) == DropItem(1)
    assert not isinstance(choose(game, RECKLESS), DropItem)


def test_a_find_buried_under_one_it_cannot_take_is_left_alone() -> None:
    pile = [
        FloorItem(Pos(3, 1), Item("torch", 1, 1)),
        FloorItem(Pos(3, 1), Item("memo", 1, 0, 0, 3)),
    ]
    game = make_game(HALL, floor=pile, pack=[Item("torch", 3, 2)])  # a full load of torches
    memory = Memory()
    assert _nearest_find(game, CAREFUL, memory) is None
    game.player.pos = Pos(3, 1)
    assert not isinstance(choose(game, CAREFUL, memory), Pickup)


def test_it_keeps_to_the_find_it_set_out_for() -> None:
    nuggets = [
        FloorItem(Pos(2, 1), Item("silver_nugget")),
        FloorItem(Pos(8, 1), Item("silver_nugget")),
    ]
    game = make_game(HALL, floor=nuggets)
    game.player.pos = Pos(5, 1)
    memory = Memory()
    assert _nearest_find(game, CAREFUL, memory) == Pos(2, 1)
    game.player.pos = Pos(7, 1)  # the other one is nearer now, but we are on our way
    assert _nearest_find(game, CAREFUL, memory) == Pos(2, 1)
    game.floor.pop(0)  # taken: on to the next
    assert _nearest_find(game, CAREFUL, memory) == Pos(8, 1)


def test_it_still_takes_documents_and_valuables() -> None:
    items = [
        FloorItem(Pos(3, 1), Item("memo", 1, 0, 0, 2)),
        FloorItem(Pos(6, 1), Item("rough_gem")),
    ]
    game = make_game(HALL, floor=items)
    assert _nearest_find(game, CAREFUL, Memory()) == Pos(3, 1)
