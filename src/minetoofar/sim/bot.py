"""A deterministic scripted player: hunts every beast and undead it can find, then walks to the
Down Shaft. It uses its class ability whenever one is ready and an enemy is within reach.

It sees the whole map (it is a test and balance tool, not an opponent), so a run is a pure
function of the seed and rank, which is what replay logs and the balance simulator need. It
goes round the traps and open graves it knows about, leaves the Rogue Humans alone unless they
come for it, and never walks into a tile where something unseen is lurking.
"""

from collections.abc import Callable

from minetoofar.core.geometry import DIRS8, Pos, octile
from minetoofar.core.grid import Tile
from minetoofar.core.pathing import distance_map
from minetoofar.sim.events import Command, Event, Move, UseAbility
from minetoofar.sim.game import Game


def _hazards(game: Game) -> set[Pos]:
    """Tiles to go round: traps, open graves, and anything hidden in the way."""
    lurking = {m.pos for m in game.monsters if m.hidden}
    graves = {
        Pos(x, y)
        for y in range(game.spec.height)
        for x in range(game.spec.width)
        if game.grid.get(x, y) == Tile.OPEN_GRAVE
    }
    return lurking | graves | {t.pos for t in game.traps if not t.disarmed}


def _step_toward(game: Game, goal: Pos, avoid: set[Pos]) -> Move | None:
    """The step that descends the distance map from `goal`; stepping onto a monster attacks it."""
    dist = distance_map(game.grid, goal, until=[game.pos])
    here = dist.get(game.pos)
    if here is None:
        return None
    best: tuple[int, int] | None = None
    for index, d in enumerate(DIRS8):
        nxt = game.pos.step(d)
        if nxt in avoid and nxt != goal:
            continue
        if game.grid.can_step(game.pos, d) and dist.get(nxt, here) < here:
            if best is None or (dist[nxt], index) < best:
                best = (dist[nxt], index)
    return Move(*DIRS8[best[1]]) if best else None


def choose(game: Game) -> Command | None:
    """The next command, or None when the run is over (dead, or standing on the Down Shaft)."""
    if game.dead:
        return None
    beside = game.adjacent_enemies()
    if beside:  # whoever is on top of us gets dealt with first, humans included
        if game.view().hero.ability.ready:
            return UseAbility()  # Cleave, a fresh coat of poison, or Dual Strike
        weakest = min(beside, key=lambda m: (m.hp, m.id))
        return Move(weakest.pos.x - game.pos.x, weakest.pos.y - game.pos.y)
    prey = [m.pos for m in game.monsters if not m.hidden and m.faction != "human"]
    if prey:
        goal = min(prey, key=lambda p: (octile(game.pos, p), p.y, p.x))
    elif game.pos != game.spec.exit:
        goal = game.spec.exit
    else:
        return None
    careful = _step_toward(game, goal, _hazards(game))
    if careful is not None:
        return careful
    lurking = {m.pos for m in game.monsters if m.hidden}
    return _step_toward(game, goal, lurking)  # no safe way: take the risk


def play(game: Game, submit: Callable[[Command], list[Event]], limit: int) -> int:
    """Play until the run ends or `limit` commands; returns how many were sent."""
    sent = 0
    while sent < limit and (command := choose(game)) is not None:
        submit(command)
        sent += 1
    return sent
