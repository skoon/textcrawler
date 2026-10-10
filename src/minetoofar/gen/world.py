"""A whole generated level: every stage in order, each from its own stream (GDD 10.4)."""

from dataclasses import dataclass
from typing import Protocol

from minetoofar.content.balance import Balance, load_balance
from minetoofar.content.gamedata import GameData, load_gamedata
from minetoofar.core.seed import Seed
from minetoofar.gen.features import Features, apply_features, generate_features
from minetoofar.gen.humans import Humans, generate_humans
from minetoofar.gen.layout import generate_level
from minetoofar.gen.level_spec import LevelSpec
from minetoofar.gen.spawns import SpawnList, generate_spawns
from minetoofar.gen.theme import Theme, generate_theme
from minetoofar.gen.traps import Traps, generate_traps

STAGES = ("layout", "theme", "features", "humans", "traps", "spawns")  # golden-tested outputs


class Stage(Protocol):
    @property
    def sha256(self) -> str: ...

    def dump(self) -> str: ...


@dataclass(frozen=True)
class World:
    layout: LevelSpec  # the bare layout (what the `layout` golden hashes)
    theme: Theme
    features: Features
    spec: LevelSpec  # the layout with its features laid in: the map the game is played on
    humans: Humans
    traps: Traps
    spawns: SpawnList  # the monsters, not counting the Rogue Human

    @property
    def room_kinds(self) -> tuple[str, ...]:
        """Room types with the human's lair merged in."""
        kinds = list(self.features.room_kinds)
        kinds[self.humans.room_id] = self.humans.room_kind
        return tuple(kinds)

    def stage(self, name: str) -> "Stage":
        """The output of one generation stage: it has a canonical `dump()` and its `sha256`."""
        stages: dict[str, Stage] = {
            "layout": self.layout, "theme": self.theme, "features": self.features,
            "humans": self.humans, "traps": self.traps, "spawns": self.spawns,
        }  # fmt: skip
        return stages[name]

    @property
    def monsters(self) -> SpawnList:
        """Everything that starts alive, in the order the game numbers them: the human first."""
        return SpawnList(
            self.spawns.seed, self.spawns.level, (self.humans.spawn(), *self.spawns.spawns)
        )


def generate_world(
    seed: Seed,
    level: int,
    balance: Balance | None = None,
    data: GameData | None = None,
    theme: Theme | None = None,
) -> World:
    """Pure function of (seed, level). `theme` overrides the roll, for tests."""
    bal, game_data = balance or load_balance(), data or load_gamedata()
    layout = generate_level(seed, level, bal)
    chosen = theme or generate_theme(seed, level)
    features = generate_features(seed, level, layout, chosen)
    spec = apply_features(layout, features)
    humans = generate_humans(seed, level, spec, features, chosen)
    traps = generate_traps(seed, level, spec, features, humans)
    spawns = generate_spawns(seed, level, spec, features, chosen, humans, game_data)
    return World(layout, chosen, features, spec, humans, traps, spawns)
