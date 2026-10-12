"""The check-in between levels (GDD 3, 5.3, 8.5): the field report, the promotion, the Wellness
Break, and the Requisitions Desk. It works on a copy of the Associate, so nothing it does can
reach back into the level just finished."""

import copy
from dataclasses import dataclass, replace

from minetoofar.content.balance import LEVELS
from minetoofar.content.desk import DeskItem, load_desk
from minetoofar.content.gamedata import RANKS
from minetoofar.core.seed import Seed
from minetoofar.gen.desk import Memo, generate_desk
from minetoofar.sim.actors import Item, max_hp
from minetoofar.sim.game import Carry, Game
from minetoofar.sim.items import KIT, TORCH, add_item, carried
from minetoofar.sim.views import TICKS_PER_TURN


@dataclass(frozen=True)
class FieldReport:
    level: int
    undead: int  # Persistent Personnel resolved
    beasts: int  # Wildlife Interface Events resolved
    human: str  # the level's Rogue Human
    human_down: bool
    valuables: int  # turned in
    turns: int
    hp: int  # the Wellness Break restores to this ...
    max_hp: int
    issued: tuple[tuple[str, int], ...]  # ... and Standard Issue tops up with these
    promoted_to: int  # 0 when there is no promotion
    unlocked: str  # the ability the new Rank unlocks, if it does


@dataclass(frozen=True)
class Purchase:
    ok: bool
    reason: str = ""  # on_hold | sold | poor | no_room | capped | have_it


def promoted_rank(game: Game) -> int:
    """Rank after this check-in: one for each level finished, never lower than you came."""
    return max(game.player.rank, min(RANKS, game.spec.level + 1))


def field_report(game: Game) -> FieldReport:
    """The report on the level as it stands, before the slip is signed."""
    p, data = game.player, game.data
    rank = promoted_rank(game)
    ability = data.abilities[data.classes[p.class_id].ability]
    issue = {KIT: game.play.issue_kits, TORCH: game.play.issue_torches}
    issued = tuple(
        (data.items.name(item), want - carried(p.pack, item))
        for item, want in issue.items()
        if want > carried(p.pack, item)
    )
    top = max_hp(data, p.class_id, rank, p.trinket, p.hp_bonus)
    return FieldReport(
        game.spec.level,
        game.ledger.undead_kills,
        game.ledger.beast_kills,
        game.human_name,
        game.ledger.bounty,
        sum(s.count for s in game.ledger.salvage),
        game.ticks // TICKS_PER_TURN,
        top,
        top,
        issued,
        rank if rank > p.rank else 0,
        ability.name if p.rank < ability.unlock_rank <= rank else "",
    )


class Checkin:
    """The memo and the desk for the level just left. Build it after `Game.check_out`."""

    def __init__(self, game: Game) -> None:
        if game.dead:
            raise ValueError("the dead do not check in")
        if game.spec.level >= LEVELS:
            raise ValueError("there is no check-in after the last level")
        self.game_data = game.data
        carry = game.carry_over()
        self.player, self.account = carry.player, carry.account
        self.cleared, self.bounties, self.turns = carry.cleared, carry.bounties, carry.turns
        self.level = game.spec.level
        self.player.rank = promoted_rank(game)
        self.player.max_hp = self.player.hp = max_hp(
            self.game_data, self.player.class_id, self.player.rank, self.player.trinket,
            self.player.hp_bonus,
        )  # fmt: skip
        desk = generate_desk(Seed(game.spec.seed), self.level)
        self.stock: list[str] = list(desk.stock)
        self.memo: Memo | None = desk.memo
        self.catalog = load_desk()
        self.sold: set[int] = set()

    @property
    def open(self) -> bool:
        """The desk is closed to an account in debt."""
        return not self.account.on_hold

    def offer(self, slot: int) -> DeskItem:
        return self.catalog[self.stock[slot]]

    def price(self, slot: int) -> int:
        return self.offer(slot).price

    def buy(self, slot: int) -> Purchase:
        """Pay for what is in `slot`. A refusal changes nothing and costs nothing."""
        item = self.offer(slot)  # an unknown slot raises IndexError
        if not self.open:
            return Purchase(False, "on_hold")
        if slot in self.sold:
            return Purchase(False, "sold")
        if self.account.wallet < item.price:
            return Purchase(False, "poor")
        refused = self._apply(item)
        if refused:
            return Purchase(False, refused)
        self.account = replace(self.account, wallet=self.account.wallet - item.price)
        self.sold.add(slot)
        return Purchase(True)

    def _apply(self, item: DeskItem) -> str:
        """Do what the item does; the reason it could not be done, or "" when it was."""
        p, a = self.player, self.account
        match item.effect:
            case "bundle":
                if not add_item(p.pack, self.game_data, Item(item.item, item.qty, 0)):
                    return "no_room"
            case "item":
                p.pack.append(Item(item.item))
            case "weapon_dmg" | "weapon_atk":
                dmg, atk = p.weapon_mods.get(p.weapon, (0, 0))
                now = dmg if item.effect == "weapon_dmg" else atk
                if now + item.value > item.cap:
                    return "capped"
                edge = (
                    (dmg + item.value, atk)
                    if item.effect == "weapon_dmg"
                    else (dmg, atk + item.value)
                )
                p.weapon_mods[p.weapon] = edge
            case "plating":
                if p.body in p.plated:
                    return "have_it"
                p.plated.add(p.body)
                p.body_dur += item.value
            case "max_hp":
                p.hp_bonus += item.value
                p.max_hp += item.value
                p.hp += item.value
            case "repair_plan" | "damage_waiver" | "hazard_waiver":
                if getattr(a, item.effect):
                    return "have_it"
                self.account = replace(a, **{item.effect: True})
        return ""

    def finish(self) -> Carry:
        """Down the Shaft, with whatever was bought."""
        return Carry(
            copy.deepcopy(self.player), self.account, self.cleared, self.bounties, self.turns
        )
