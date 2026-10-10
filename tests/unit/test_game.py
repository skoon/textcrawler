import pytest

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Tile
from minetoofar.core.seed import Seed
from minetoofar.sim.events import (
    Blocked,
    BlockReason,
    DoorOpened,
    Move,
    Moved,
    Run,
    ToggleTorch,
    TorchChanged,
    Wait,
    Waited,
)
from minetoofar.sim.game import REMEMBERED, UNSEEN, VISIBLE, Game
from tests.helpers import make_game

E, S, SE, W = Move(1, 0), Move(0, 1), Move(1, 1), Move(-1, 0)


def game(rows: list[str]) -> Game:
    return make_game(rows)


def vis(g: Game, x: int, y: int) -> int:
    view = g.view()
    return view.vis[y * view.width + x]


def test_new_game_starts_on_the_entry_stairs_with_the_hard_hat_lit() -> None:
    g = Game.new(Seed.parse("BRASSLAMP42"), 1)
    view = g.view()
    assert view.player == g.spec.entry and view.ticks == 0 and view.turn == 0
    assert view.light_radius == 4 and view.torch_lit is False
    assert vis(g, view.player.x, view.player.y) == VISIBLE
    assert (view.level, view.seed) == (1, "BRASSLAMP42")


def test_moving_costs_one_turn_and_changes_position() -> None:
    g = game(["####", "#<.#", "####"])
    assert g.submit(E) == [Moved(Pos(2, 1), Tile.FLOOR)]
    assert g.pos == Pos(2, 1) and g.ticks == 100 and g.view().turn == 1


def test_walking_into_a_wall_is_refused_without_spending_time() -> None:
    g = game(["####", "#<.#", "####"])
    assert g.submit(W) == [Blocked(Pos(0, 1), BlockReason.WALL)]
    assert g.pos == Pos(1, 1) and g.ticks == 0


def test_diagonals_cannot_cut_corners() -> None:
    g = game(["####", "#<##", "#..#", "####"])
    assert g.submit(SE) == [Blocked(Pos(2, 2), BlockReason.CORNER)]
    assert g.ticks == 0


def test_diagonal_into_a_door_is_refused_orthogonal_opens_it() -> None:
    g = game(["#####", "#<..#", "#.+.#", "#...#", "#####"])
    assert g.submit(SE) == [Blocked(Pos(2, 2), BlockReason.DOOR)]
    g.submit(E)
    assert g.submit(S) == [DoorOpened(Pos(2, 2))]
    assert g.pos == Pos(2, 1) and g.ticks == 200  # one step, one door
    assert g.submit(S) == [Moved(Pos(2, 2), Tile.DOOR_OPEN)]


def test_bumping_a_door_opens_it_in_the_level_state_only() -> None:
    g = game(["#####", "#<+.#", "#####"])
    g.submit(E)
    assert Tile(g.view().tiles[1 * 5 + 2]) == Tile.DOOR_OPEN
    assert g.spec.tiles[1 * 5 + 2] == Tile.DOOR  # the immutable spec is untouched


def test_closed_door_blocks_sight_until_opened() -> None:
    g = game(["#########", "#<..+...#", "#########"])
    assert vis(g, 4, 1) == VISIBLE and vis(g, 5, 1) == UNSEEN
    g.submit(E)
    g.submit(E)
    assert vis(g, 5, 1) == UNSEEN
    g.submit(E)  # opens the door
    assert vis(g, 5, 1) == VISIBLE and vis(g, 7, 1) == VISIBLE


def test_tiles_leaving_view_are_remembered_not_forgotten() -> None:
    g = game(["#############", "#<..........#", "#############"])
    assert vis(g, 5, 1) == VISIBLE and vis(g, 6, 1) == UNSEEN
    for _ in range(6):
        g.submit(E)
    assert vis(g, 1, 1) == REMEMBERED and vis(g, 6, 1) == VISIBLE
    assert vis(g, 11, 1) == VISIBLE and vis(g, 12, 1) == UNSEEN


def test_torch_widens_the_light_and_costs_a_turn() -> None:
    g = game(["#############", "#<..........#", "#############"])
    assert g.submit(ToggleTorch()) == [TorchChanged(True)]
    view = g.view()
    assert view.torch_lit and view.light_radius == 8 and view.ticks == 100
    assert vis(g, 9, 1) == VISIBLE and vis(g, 10, 1) == UNSEEN
    assert g.submit(ToggleTorch()) == [TorchChanged(False)]
    assert g.view().light_radius == 4 and vis(g, 9, 1) == REMEMBERED


def test_waiting_costs_a_turn() -> None:
    g = game(["###", "#<#", "###"])
    assert g.submit(Wait()) == [Waited()]
    assert g.ticks == 100


@pytest.mark.parametrize("bad", [(0, 0), (2, 0), (1, -2)])
def test_invalid_direction_fails_loudly(bad: tuple[int, int]) -> None:
    g = game(["###", "#<#", "###"])
    with pytest.raises(ValueError):
        g.submit(Move(*bad))
    with pytest.raises(ValueError):
        g.submit(Run(*bad))


def test_run_follows_a_corridor_to_its_end() -> None:
    g = game(["########", "#<.....#", "########"])
    events = g.submit(Run(1, 0))
    assert g.pos == Pos(6, 1) and g.ticks == 500
    assert events == [Moved(Pos(x, 1), Tile.FLOOR) for x in range(2, 7)]


def test_run_stops_at_a_side_opening() -> None:
    g = game(["#########", "#<......#", "####.####", "####.####", "#########"])
    g.submit(Run(1, 0))
    assert g.pos == Pos(4, 1)


def test_run_opens_a_door_then_stops_on_it() -> None:
    g = game(["########", "#<..+..#", "########"])
    assert g.submit(Run(1, 0))[-1] == DoorOpened(Pos(4, 1))
    assert g.pos == Pos(3, 1)
    assert g.submit(Run(1, 0)) == [Moved(Pos(4, 1), Tile.DOOR_OPEN)]
    g.submit(Run(1, 0))
    assert g.pos == Pos(6, 1)


def test_run_across_a_room_stops_at_the_far_wall_without_complaint() -> None:
    g = game(["#######", "#<....#", "#.....#", "#.....#", "#######"])
    events = g.submit(Run(1, 0))
    assert g.pos == Pos(5, 1) and g.ticks == 400
    assert all(isinstance(e, Moved) for e in events)


def test_run_into_a_wall_reports_it_like_a_plain_move() -> None:
    g = game(["####", "#<.#", "####"])
    assert g.submit(Run(-1, 0)) == [Blocked(Pos(0, 1), BlockReason.WALL)]
    assert g.ticks == 0


def test_run_stops_on_special_tiles() -> None:
    g = game(["########", "#<..>..#", "########"])
    g.submit(Run(1, 0))
    assert g.pos == Pos(4, 1)


def test_new_game_carries_worn_armor_in_and_rejects_impossible_values() -> None:
    from minetoofar.core.seed import Seed

    seed = Seed.parse("BRASSLAMP42")
    full = Game.new(seed, 2).player.body_dur
    assert Game.new(seed, 2, armor_dur=full - 3).player.body_dur == full - 3
    assert Game.new(seed, 2, armor_dur=0).player.body_dur == 0
    for bad in (-1, full + 1):
        with pytest.raises(ValueError, match="armor_dur"):
            Game.new(seed, 2, armor_dur=bad)
