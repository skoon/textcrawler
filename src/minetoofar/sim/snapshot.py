"""Game state as plain JSON data and back (GDD 11): everything that changes during play, and
nothing that the seed regenerates. A restored game is indistinguishable from the one saved: the
tests prove it by playing both on and comparing state hashes."""

import base64
from typing import Any

from minetoofar.core.geometry import Pos
from minetoofar.core.grid import Grid, Tile
from minetoofar.core.seed import Seed
from minetoofar.gen.drops import SupplyLine
from minetoofar.sim.actors import FloorItem, Item, Monster, Player, StatusState
from minetoofar.sim.combat import Stats
from minetoofar.sim.economy import Account
from minetoofar.sim.game import Carry, Game
from minetoofar.sim.ledger import Ledger, Repair, Salvage, Use
from minetoofar.sim.supply import Crate
from minetoofar.sim.traps import Trap

Json = dict[str, Any]


class SnapshotError(ValueError):
    """The data does not describe a game this build can restore."""


# -- small pieces ----------------------------------------------------------------------------


def _pos(p: Pos) -> list[int]:
    return [p.x, p.y]


def _unpos(raw: Any) -> Pos:
    x, y = raw
    return Pos(_int(x), _int(y))


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SnapshotError(f"expected a whole number, got {value!r}")
    return value


def _statuses(d: dict[str, StatusState]) -> dict[str, list[int]]:
    return {k: [s.ends, s.power, s.charges, s.next_tick] for k, s in d.items()}


def _unstatuses(raw: dict[str, list[int]]) -> dict[str, StatusState]:
    return {k: StatusState(*(_int(v) for v in vals)) for k, vals in raw.items()}


def _item(i: Item) -> list[Any]:
    return [i.id, i.qty, i.charge, i.dur, i.text]


def _unitem(raw: Any) -> Item:
    ident, *numbers = raw
    if not isinstance(ident, str):
        raise SnapshotError(f"an item needs a name, got {ident!r}")
    return Item(ident, *(_int(n) for n in numbers))


# -- the Associate ---------------------------------------------------------------------------


def player_to_dict(p: Player) -> Json:
    return {
        "name": p.name, "pos": _pos(p.pos), "hp": p.hp, "max_hp": p.max_hp, "ready_at": p.ready_at,
        "facing": list(p.facing), "statuses": _statuses(p.statuses), "immune": dict(p.immune),
        "class_id": p.class_id, "rank": p.rank, "weapon": p.weapon, "offhand": p.offhand,
        "head": p.head, "body": p.body, "body_dur": p.body_dur, "stubborn_used": p.stubborn_used,
        "trinket": p.trinket, "pack": [_item(i) for i in p.pack], "torch_left": p.torch_left,
        "hp_bonus": p.hp_bonus,
        "weapon_mods": {k: list(v) for k, v in sorted(p.weapon_mods.items())},
        "plated": sorted(p.plated),
    }  # fmt: skip


def player_from_dict(d: Json) -> Player:
    return Player(
        id=0, name=d["name"], pos=_unpos(d["pos"]), hp=_int(d["hp"]), max_hp=_int(d["max_hp"]),
        ready_at=_int(d["ready_at"]), facing=(_int(d["facing"][0]), _int(d["facing"][1])),
        statuses=_unstatuses(d["statuses"]), immune={k: _int(v) for k, v in d["immune"].items()},
        class_id=d["class_id"], rank=_int(d["rank"]), weapon=d["weapon"], offhand=d["offhand"],
        head=d["head"], body=d["body"], body_dur=_int(d["body_dur"]),
        stubborn_used=bool(d["stubborn_used"]), trinket=d["trinket"],
        pack=[_unitem(i) for i in d["pack"]], torch_left=_int(d["torch_left"]),
        hp_bonus=_int(d["hp_bonus"]),
        weapon_mods={k: (_int(v[0]), _int(v[1])) for k, v in d["weapon_mods"].items()},
        plated=set(d["plated"]),
    )  # fmt: skip


def account_to_dict(a: Account) -> Json:
    return {
        "wallet": a.wallet, "debt": a.debt, "repair_plan": a.repair_plan,
        "hazard_waiver": a.hazard_waiver, "damage_waiver": a.damage_waiver, "coupons": a.coupons,
    }  # fmt: skip


def account_from_dict(d: Json) -> Account:
    return Account(
        _int(d["wallet"]), _int(d["debt"]), bool(d["repair_plan"]), bool(d["hazard_waiver"]),
        bool(d["damage_waiver"]), _int(d["coupons"]),
    )  # fmt: skip


def carry_to_dict(c: Carry) -> Json:
    return {
        "player": player_to_dict(c.player), "account": account_to_dict(c.account),
        "cleared": c.cleared, "bounties": c.bounties, "turns": c.turns,
    }  # fmt: skip


def carry_from_dict(d: Json) -> Carry:
    try:
        return Carry(
            player_from_dict(d["player"]), account_from_dict(d["account"]),
            _int(d["cleared"]), _int(d["bounties"]), _int(d["turns"]),
        )  # fmt: skip
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as err:
        raise SnapshotError(f"unreadable carry-over: {err!r}") from err


def _repair(r: Repair) -> list[Any]:
    return [r.name, r.missing, r.rate]


def _ledger_to_dict(led: Ledger) -> Json:
    return {
        "level": led.level, "graveyard": led.graveyard, "died": led.died, "bounty": led.bounty,
        "salvage": [[s.kind, s.name, s.credit, s.count] for s in led.salvage],
        "used": [[u.item, u.name, u.charge, u.count] for u in led.used],
        "traps": led.traps, "tripwires": led.tripwires, "torches_dropped": led.torches_dropped,
        "clock_ins": led.clock_ins, "undead_kills": led.undead_kills,
        "beast_kills": led.beast_kills, "stubborn": led.stubborn,
        "repair": None if led.repair is None else _repair(led.repair),
        "lanyard": led.lanyard, "supply": [[label, gold] for label, gold in led.supply],
    }  # fmt: skip


def _ledger_from_dict(d: Json) -> Ledger:
    repair = d["repair"]
    return Ledger(
        level=_int(d["level"]), graveyard=bool(d["graveyard"]), died=bool(d["died"]),
        bounty=bool(d["bounty"]),
        salvage=[Salvage(k, n, _int(c), _int(q)) for k, n, c, q in d["salvage"]],
        used=[Use(i, n, _int(c), _int(q)) for i, n, c, q in d["used"]],
        traps=_int(d["traps"]), tripwires=_int(d["tripwires"]),
        torches_dropped=_int(d["torches_dropped"]), clock_ins=_int(d["clock_ins"]),
        undead_kills=_int(d["undead_kills"]), beast_kills=_int(d["beast_kills"]),
        stubborn=bool(d["stubborn"]),
        repair=None if repair is None else Repair(repair[0], _int(repair[1]), _int(repair[2])),
        lanyard=bool(d["lanyard"]), supply=[(label, _int(gold)) for label, gold in d["supply"]],
    )  # fmt: skip


# -- the monsters ------------------------------------------------------------------------------

_STATS = ("atk", "defense", "dr", "dice_n", "dice_sides", "dmg_flat", "attack_cost")


def _monster_to_dict(m: Monster) -> Json:
    return {
        "id": m.id, "name": m.name, "pos": _pos(m.pos), "hp": m.hp, "max_hp": m.max_hp,
        "ready_at": m.ready_at, "facing": list(m.facing), "statuses": _statuses(m.statuses),
        "immune": dict(m.immune), "kind": m.kind, "behavior": m.behavior, "faction": m.faction,
        "state": m.state, "stats": [getattr(m.stats, k) for k in _STATS] + [m.stats.stuns],
        "move_cost": m.move_cost, "sight": m.sight,
        "alert_pos": None if m.alert_pos is None else _pos(m.alert_pos), "since": m.since,
        "unseen_since": m.unseen_since, "last_trap": m.last_trap, "traps_left": m.traps_left,
        "speech": dict(m.speech), "said": dict(m.said),
    }  # fmt: skip


def _monster_from_dict(d: Json) -> Monster:
    atk, defense, dr, dice_n, dice_sides, dmg_flat, attack_cost, stuns = d["stats"]
    stats = Stats(
        _int(atk), _int(defense), _int(dr), _int(dice_n), _int(dice_sides), _int(dmg_flat),
        _int(attack_cost), bool(stuns),
    )  # fmt: skip
    alert = d["alert_pos"]
    unseen = d["unseen_since"]
    return Monster(
        id=_int(d["id"]), name=d["name"], pos=_unpos(d["pos"]), hp=_int(d["hp"]),
        max_hp=_int(d["max_hp"]), ready_at=_int(d["ready_at"]),
        facing=(_int(d["facing"][0]), _int(d["facing"][1])), statuses=_unstatuses(d["statuses"]),
        immune={k: _int(v) for k, v in d["immune"].items()}, kind=d["kind"],
        behavior=d["behavior"], faction=d["faction"], state=d["state"], stats=stats,
        move_cost=_int(d["move_cost"]), sight=_int(d["sight"]),
        alert_pos=None if alert is None else _unpos(alert), since=_int(d["since"]),
        unseen_since=None if unseen is None else _int(unseen), last_trap=_int(d["last_trap"]),
        traps_left=_int(d["traps_left"]), speech=dict(d["speech"]),
        said={k: _int(v) for k, v in d["said"].items()},
    )  # fmt: skip


# -- the level in play -------------------------------------------------------------------------


def _crate_lines(c: Crate) -> list[list[Any]]:
    return [[ln.item, ln.qty, ln.dur] for ln in c.lines]


def game_to_dict(g: Game) -> Json:
    """Everything that has changed since `Game.new` for this seed and level."""
    fresh = g.spec.tiles
    now = g.grid.to_bytes()
    width = g.spec.width
    changed = [[i % width, i // width, now[i]] for i in range(len(now)) if now[i] != fresh[i]]
    return {
        "seed": g.spec.seed, "level": g.spec.level, "rng": g.rng.state,
        "player": player_to_dict(g.player),
        "monsters": [_monster_to_dict(m) for m in g.monsters],
        "traps": [[*_pos(t.pos), t.kind, t.revealed, t.disarmed] for t in g.traps],
        "floor": [[*_pos(f.pos), *_item(f.item)] for f in g.floor],
        "drops": [[mid, [_item(i) for i in items]] for mid, items in sorted(g.drops.items())],
        "crates": [
            [*_pos(c.pos), c.number, _crate_lines(c), c.delivery_billed]
            for c in g.crates
        ],
        "due": [number for number, _ in g._due],
        "tiles_changed": changed,
        "torch_lit": g.torch_lit, "dead": g.dead, "cause": g.cause,
        "vis": base64.b64encode(bytes(g._vis)).decode("ascii"),
        "spotted": sorted(g._spotted), "spot_tick": g._spot_tick,
        "account": account_to_dict(g.account), "ledger": _ledger_to_dict(g.ledger),
        "cleared": g.cleared, "bounties": g.bounties, "turns_before": g.turns_before,
    }  # fmt: skip


def game_from_dict(d: Json) -> Game:
    """Regenerate the level from its seed, then lay the saved state over it."""
    try:
        return _restore(d)
    except SnapshotError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as err:
        raise SnapshotError(f"unreadable game state: {err!r}") from err


def _restore(d: Json) -> Game:
    player = player_from_dict(d["player"])
    g = Game.new(Seed(d["seed"]), _int(d["level"]), player.rank, player.class_id)
    g.rng.state = _int(d["rng"])
    player.id = g.player.id
    g.player = player
    g.monsters = [_monster_from_dict(m) for m in d["monsters"]]
    g.traps = [
        Trap(Pos(_int(x), _int(y)), kind, bool(rev), bool(dis))
        for x, y, kind, rev, dis in d["traps"]
    ]
    g.floor = [FloorItem(Pos(_int(row[0]), _int(row[1])), _unitem(row[2:])) for row in d["floor"]]
    g.drops = {_int(mid): [_unitem(i) for i in items] for mid, items in d["drops"]}
    g.crates = [
        Crate(
            Pos(_int(x), _int(y)), _int(number),
            [SupplyLine(item, _int(qty), _int(dur)) for item, qty, dur in lines], bool(billed),
        )
        for x, y, number, lines, billed in d["crates"]
    ]  # fmt: skip
    due = set(d["due"])
    g._due = [(n, drop) for n, drop in g._due if n in due]
    grid = Grid(g.spec.width, g.spec.height, g.spec.tiles)
    for x, y, tile in d["tiles_changed"]:
        grid.set(_int(x), _int(y), Tile(_int(tile)))
    g.grid = grid
    g.torch_lit, g.dead, g.cause = bool(d["torch_lit"]), bool(d["dead"]), str(d["cause"])
    vis = bytearray(base64.b64decode(d["vis"], validate=True))
    if len(vis) != g.spec.width * g.spec.height:
        raise SnapshotError("the remembered map does not fit this mine")
    g._vis = vis
    g._spotted = {_int(i) for i in d["spotted"]}
    g._spot_tick = _int(d["spot_tick"])
    g.account = account_from_dict(d["account"])
    g.ledger = _ledger_from_dict(d["ledger"])
    g.cleared, g.bounties = _int(d["cleared"]), _int(d["bounties"])
    g.turns_before = _int(d["turns_before"])
    g._dist = g._flee = None
    return g
