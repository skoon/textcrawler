"""The pack (GDD 8.2): consumable stacks are kept apart by their use charge, so the pay slip can
tell issued, found, and prepaid stock apart."""

from collections.abc import Mapping

from minetoofar.content.gamedata import GameData
from minetoofar.sim.actors import Item

KIT = "patch_up_kit"  # the two things Standard Issue hands out (GDD 8.2)
TORCH = "torch"


def carried(pack: list[Item], item_id: str) -> int:
    return sum(i.qty for i in pack if i.id == item_id)


def add_item(pack: list[Item], data: GameData, item: Item) -> bool:
    """Put `item` in the pack; False (and no change) if a carry limit would be passed."""
    limit = data.items.consumables[item.id].carry if item.id in data.items.consumables else None
    if limit is None:
        pack.append(item)  # equipment: one to a slot, no limit
        return True
    if carried(pack, item.id) + item.qty > limit:
        return False
    for stack in pack:
        if stack.id == item.id and stack.charge == item.charge:
            stack.qty += item.qty
            return True
    pack.append(item)
    return True


def remove_one(pack: list[Item], index: int) -> Item:
    """Take a single unit out of a slot, with its charge and condition."""
    stack = pack[index]
    one = Item(stack.id, 1, stack.charge, stack.dur)
    stack.qty -= 1
    if stack.qty == 0:
        del pack[index]
    return one


def standard_issue(pack: list[Item], data: GameData, issue: Mapping[str, int]) -> None:
    """Top the pack up to the issued counts with stock billed at list price."""
    for item_id, want in issue.items():
        short = want - carried(pack, item_id)
        if short > 0:
            add_item(pack, data, Item(item_id, short, data.items.consumables[item_id].price))
