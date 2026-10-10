"""The level's theme roll (GDD 9.4, 9.6, 10.4 step 1): graveyard or not, and which Rogue Human."""

import hashlib
from dataclasses import dataclass

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.speech import MOODS
from minetoofar.core.seed import Seed

HUMANS = ("foreman_grimsby", "prospector_vane")


@dataclass(frozen=True)
class Theme:
    seed: str
    level: int
    graveyard: bool
    human: str
    mood: str
    tic_roll: int  # picks the human's tic from its list, modulo the list's length

    def dump(self) -> str:
        lines = [
            "AMTF-THEME",
            f"seed {self.seed}",
            f"level {self.level}",
            f"graveyard {int(self.graveyard)}",
            f"human {self.human}",
            f"mood {self.mood}",
            f"tic_roll {self.tic_roll}",
        ]
        return "\n".join(lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dump().encode("ascii")).hexdigest()


def generate_theme(seed: Seed, level: int) -> Theme:
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1-{LEVELS}, got {level}")
    p = load_balance().theme
    rng = seed.rng().derive("level", level, "theme")
    graveyard = rng.chance(p.graveyard_pct, 100)
    human = HUMANS[0] if rng.chance(p.grimsby_pct, 100) else HUMANS[1]
    mood = rng.pick(MOODS)
    return Theme(seed.canonical, level, graveyard, human, mood, rng.below(1000))
