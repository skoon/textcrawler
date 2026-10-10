"""Actors: the player and the monsters, plus the arithmetic that turns kit and rank into Stats."""

from dataclasses import dataclass, field

from minetoofar.content.gamedata import GameData, MonsterDef
from minetoofar.core.geometry import Pos
from minetoofar.sim.combat import Stats

PLAYER_ID = 0
NEVER = 1 << 60  # "ends" for a status with no time limit
SOUTH = (0, 1)
OFFHAND_PENALTY = 4  # GDD 6.7


@dataclass
class StatusState:
    ends: int  # the tick it ends
    power: int = 0  # strength, e.g. Poisoned damage per tick
    charges: int = 0  # Coated: weapon hits left
    next_tick: int = 0  # tick statuses: when the next tick lands


@dataclass(kw_only=True)
class Actor:
    id: int
    name: str
    pos: Pos
    hp: int
    max_hp: int
    ready_at: int = 0
    facing: tuple[int, int] = SOUTH  # set by the last move or attack (GDD 7.4)
    statuses: dict[str, StatusState] = field(default_factory=dict)
    immune: dict[str, int] = field(default_factory=dict)  # status id -> tick immunity ends


@dataclass(kw_only=True)
class Player(Actor):
    class_id: str
    rank: int
    weapon: str
    offhand: str
    head: str
    body: str
    body_dur: int
    stubborn_used: bool = False


@dataclass(kw_only=True)
class Monster(Actor):
    kind: str
    behavior: str
    faction: str
    state: str  # asleep | idle | alerted | hunting | fleeing | buried | submerged
    stats: Stats
    move_cost: int
    sight: int
    alert_pos: Pos | None = None  # where a noise came from, for the Alerted state
    since: int = 0  # Eel: last tick it had a target beside it; Vane: when his retreat began
    unseen_since: int | None = None  # fleeing Badger: when it dropped out of the player's sight
    last_trap: int = -(10**9)  # Vane: when he last laid a trap
    traps_left: int = 0  # Vane: traps still in his pack
    speech: dict[str, str] = field(default_factory=dict)  # humans: event -> line
    said: dict[str, int] = field(default_factory=dict)  # speech event -> tick it was last said

    @property
    def hidden(self) -> bool:
        """Buried or submerged: invisible and untargetable until it surfaces."""
        return self.state in ("buried", "submerged")


def modifier(score: int) -> int:
    return (score - 10) // 2


def _rank_index(rank: int) -> int:
    if not 1 <= rank <= 5:
        raise ValueError(f"rank must be 1-5, got {rank}")
    return rank - 1


def max_hp(data: GameData, class_id: str, rank: int) -> int:
    return data.classes[class_id].rank_hp[_rank_index(rank)]


def new_player(data: GameData, class_id: str, rank: int, pos: Pos) -> Player:
    c = data.classes[class_id]
    hp = max_hp(data, class_id, rank)
    return Player(
        id=PLAYER_ID, name=c.default_name, pos=pos, hp=hp, max_hp=hp,
        class_id=class_id, rank=rank, weapon=c.weapon, offhand=c.offhand, head=c.head,
        body=c.body, body_dur=data.items.armor[c.body].dur,
    )  # fmt: skip


def _weapon_stat_mod(data: GameData, class_id: str, weapon_id: str) -> int:
    c = data.classes[class_id]
    str_mod, dex_mod = modifier(c.strength), modifier(c.dexterity)
    return str_mod if data.items.weapons[weapon_id].stat == "str" else max(str_mod, dex_mod)


def player_stats(player: Player, data: GameData) -> Stats:
    """ATK, DEF, DR and damage from attributes, Rank, and what is worn (GDD 6.1)."""
    c = data.classes[player.class_id]
    i = _rank_index(player.rank)
    weapon = data.items.weapons[player.weapon]
    armor = data.items.armor[player.body]
    stat_mod = _weapon_stat_mod(data, player.class_id, player.weapon)
    broken = player.body_dur <= 0
    shield = data.items.shields.get(player.offhand)
    return Stats(
        atk=2 + c.rank_atk[i] + stat_mod + weapon.atk,
        defense=modifier(c.dexterity)
        + (0 if broken else armor.defense)
        + (shield.defense if shield else 0)
        + data.items.hats[player.head].defense,
        dr=0 if broken else armor.dr,
        dice_n=weapon.dice_n,
        dice_sides=weapon.dice_sides,
        dmg_flat=stat_mod + weapon.dmg + c.rank_dmg[i],
        attack_cost=weapon.cost,
    )


def offhand_stats(player: Player, data: GameData, penalty: int = OFFHAND_PENALTY) -> Stats | None:
    """The off-hand attack of a dual wielder (GDD 6.7), or None when no second weapon is held.

    It attacks at `penalty` less ATK and its damage gets no attribute modifier."""
    off = data.items.weapons.get(player.offhand)
    main = data.items.weapons[player.weapon]
    if off is None or off.two_handed or main.two_handed:
        return None
    c = data.classes[player.class_id]
    i = _rank_index(player.rank)
    base = player_stats(player, data)
    return Stats(
        atk=2
        + c.rank_atk[i]
        + _weapon_stat_mod(data, player.class_id, player.offhand)
        + off.atk
        - penalty,
        defense=base.defense,
        dr=base.dr,
        dice_n=off.dice_n,
        dice_sides=off.dice_sides,
        dmg_flat=off.dmg + c.rank_dmg[i],
        attack_cost=off.cost,
    )


def scaled_monster_stats(m: MonsterDef, level: int) -> tuple[Stats, int]:
    """Stats and HP of a monster on `level` (GDD 7.6 level scaling)."""
    bonus = (level - 1) // 2
    stats = Stats(
        atk=m.atk + bonus, defense=m.defense, dr=m.dr, dice_n=m.dice_n,
        dice_sides=m.dice_sides, dmg_flat=m.dmg + bonus, attack_cost=m.attack_cost,
    )  # fmt: skip
    return stats, m.hp * (100 + 12 * (level - 1)) // 100


def new_monster(
    data: GameData,
    kind: str,
    ident: int,
    pos: Pos,
    state: str,
    level: int,
    facing: tuple[int, int] = SOUTH,
    speech: dict[str, str] | None = None,
    traps_left: int = 0,
) -> Monster:
    m = data.monsters[kind]
    stats, hp = scaled_monster_stats(m, level)
    return Monster(
        id=ident, name=m.name, pos=pos, hp=hp, max_hp=hp, kind=kind, behavior=m.behavior,
        faction=m.faction, state=state, stats=stats, move_cost=m.move_cost, sight=m.sight,
        facing=facing, speech=dict(speech or {}), traps_left=traps_left,
    )  # fmt: skip
