"""Read-only snapshots the UI draws from; copied so a later turn cannot change a frame."""

from dataclasses import dataclass

from minetoofar.core.geometry import Pos

TICKS_PER_TURN = 100


@dataclass(frozen=True)
class AbilityView:
    name: str
    unlock_rank: int
    unlocked: bool
    ready: bool  # unlocked and off cooldown
    cooldown_turns: int  # whole turns left, rounded up


@dataclass(frozen=True)
class HeroView:
    name: str
    class_name: str
    rank: int
    hp: int
    max_hp: int
    strength: int
    dexterity: int
    atk: int
    defense: int
    dr: int
    damage: str  # e.g. "1d8+3"
    offhand_attack: str  # e.g. "ATK -1  DMG 1d6", or "" without a second weapon
    class_id: str
    weapon: str
    offhand: str  # "" when empty
    head: str
    body: str
    armor_dur: int
    armor_max: int
    signature: str  # stubborn | backstab | tracker
    ability: AbilityView
    dead: bool
    cause: str
    trinket: str = ""  # "" when none is worn


@dataclass(frozen=True)
class MonsterView:
    id: int
    kind: str
    name: str
    pos: Pos
    hp: int
    max_hp: int


@dataclass(frozen=True)
class TrapView:
    pos: Pos
    name: str
    disarmed: bool


@dataclass(frozen=True)
class PackLine:
    index: int  # the slot, for Equip / UseItem / DropItem
    id: str
    name: str
    qty: int
    charge: int  # gold billed per use (consumables)
    category: str  # weapon | armor | shield | hat | trinket | consumable
    dur: int  # condition (armor), else 0
    dur_max: int


@dataclass(frozen=True)
class FloorView:
    pos: Pos
    id: str
    name: str
    glyph: str  # weapon | armor | trinket | consumable | silver | gem | document


@dataclass(frozen=True)
class CrateView:
    pos: Pos
    number: int


@dataclass(frozen=True)
class GameView:
    width: int
    height: int
    tiles: bytes
    vis: bytes  # UNSEEN / REMEMBERED / VISIBLE per tile
    player: Pos
    ticks: int
    light_radius: int
    torch_lit: bool
    level: int
    seed: str
    hero: HeroView
    monsters: tuple[MonsterView, ...]  # only the ones in view
    sensed: tuple[MonsterView, ...]  # the Ranger's Tracker: out of view, through walls
    traps: tuple[TrapView, ...]  # only the revealed ones
    graveyard: bool = False  # a graveyard floor gets its own palette
    pack: tuple[PackLine, ...] = ()
    floor: tuple[FloorView, ...] = ()  # finds on tiles that have been seen
    gold: int = 0
    debt: int = 0
    coupons: int = 0
    torch_turns: int = 0  # burn time left in the torch in hand, in whole turns
    crates: tuple[CrateView, ...] = ()  # landed supply crates on tiles that have been seen

    @property
    def turn(self) -> int:
        return self.ticks // TICKS_PER_TURN
