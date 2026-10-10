"""A test pack of Cave Vermin (fast, weak, beasts) against all three classes."""

import pytest

from minetoofar.core.geometry import Pos
from minetoofar.core.rng import Rng
from minetoofar.sim.bot import play
from minetoofar.sim.events import Wait
from tests.helpers import make_game

VERMIN = "cave_vermin"
ARENA = ["#" * 12, "#<" + "." * 9 + "#", *["#" + "." * 10 + "#" for _ in range(6)], "#" * 12]
PACK = [(VERMIN, (6, 2), "hunting"), (VERMIN, (7, 3), "hunting"), (VERMIN, (6, 4), "hunting"),
        (VERMIN, (8, 2), "hunting")]  # fmt: skip


def test_vermin_move_twice_as_fast_as_the_player() -> None:
    rows = ["#" * 14, "#<" + "." * 11 + "#", "#" * 14]
    g = make_game(rows, [(VERMIN, (9, 1), "hunting")])
    g.submit(Wait())  # a Vermin step costs 50: two steps before the player acts again
    assert g.monsters[0].pos == Pos(7, 1)


@pytest.mark.parametrize("class_id", ["fighter", "rogue", "ranger"])
def test_every_class_can_clear_a_pack_of_four(class_id: str) -> None:
    results = []
    for seed in range(1, 9):
        g = make_game(ARENA, PACK, Rng(seed), class_id=class_id)
        play(g, g.submit, 300)
        results.append(g)
    cleared = sum(not g.dead and not g.monsters for g in results)
    assert cleared >= 6, f"{class_id} cleared {cleared} of {len(results)} packs"
    assert all(0 <= g.player.hp <= g.player.max_hp for g in results)


def test_the_ranger_is_best_against_beasts() -> None:
    def hp_left(class_id: str) -> int:
        total = 0
        for seed in range(1, 9):
            g = make_game(ARENA, PACK, Rng(seed), class_id=class_id)
            play(g, g.submit, 300)
            total += g.player.hp
        return total

    assert hp_left("ranger") >= hp_left("rogue")  # +2 a blow and two blows a turn
