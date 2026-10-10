"""Text for the status panel (GDD 5.1). Pure functions: no Textual, so tests need no terminal."""

from minetoofar.content.gamedata import UPGRADE_RANK
from minetoofar.content.text import Text
from minetoofar.core.geometry import Pos, octile
from minetoofar.sim.actors import modifier
from minetoofar.sim.game import Game
from minetoofar.sim.views import GameView, MonsterView
from minetoofar.ui.glyphs import GlyphSet, hp_bar

WIDTH = 24  # inner width of the 28-column panel (border and padding take four)
BAR_CELLS = 12
NEARBY_SHOWN = 5


def nearby_lines(
    monsters: tuple[MonsterView, ...],
    player: Pos,
    glyphs: GlyphSet,
    sensed: tuple[MonsterView, ...] = (),
) -> list[str]:
    """Up to five enemies, the ones in view first (nearest first, with HP), then the ones the
    Tracker senses through walls (GDD 5.1), shown as `~ Name` since they cannot be inspected."""

    def nearest(group: tuple[MonsterView, ...]) -> list[MonsterView]:
        return sorted(group, key=lambda m: (octile(player, m.pos), m.id))

    out = []
    for m in nearest(monsters):
        hp = f"{m.hp}/{m.max_hp}"
        room = WIDTH - 2 - 1 - len(hp)
        out.append(f"{glyphs.monsters[m.kind]} {m.name[:room].ljust(room)} {hp}")
    out += [f"~ {m.name}"[:WIDTH] for m in nearest(sensed)]
    return out[:NEARBY_SHOWN]


def _ability_line(view: GameView) -> str:
    ab = view.hero.ability
    if not ab.unlocked:
        state = f"Rk {ab.unlock_rank}"
    else:
        state = "rdy" if ab.ready else f"{ab.cooldown_turns}t"
    return f"[a] {ab.name}  {state}"


def status_lines(view: GameView, glyphs: GlyphSet, share_code: str) -> list[str]:
    hero = view.hero
    armor = f"Armor {hero.armor_dur}/{hero.armor_max}" + (" BROKEN" if hero.armor_dur <= 0 else "")
    lamp = "Torch" if view.torch_lit else "Hard Hat"
    lines = [
        f"{hero.name} the {hero.class_name}".ljust(20) + f"Rk{hero.rank}",
        f"HP {hp_bar(hero.hp, hero.max_hp, BAR_CELLS, glyphs)} {hero.hp}/{hero.max_hp}",
        f"DEF {hero.defense}  ATK {hero.atk:+d}  DMG {hero.damage}",
        armor,
        f"Light: {lamp} ({view.light_radius})",
        _ability_line(view),
    ]
    nearby = nearby_lines(view.monsters, view.player, glyphs, view.sensed)
    if nearby:
        lines += ["", "Nearby", *nearby]
    return [*lines, "", f"Turn {view.turn}", f"Seed {share_code}"]


SHEET_WIDTH = 44


def _ability_text(game: Game, text: Text) -> str:
    ab = game.data.abilities[game.data.classes[game.player.class_id].ability]
    up = game.player.rank >= UPGRADE_RANK
    value, charges = (ab.value_up, ab.charges_up) if up else (ab.value, ab.charges)
    turns = (ab.cooldown_ticks_up if up else ab.cooldown_ticks) // 100
    if ab.kind == "cleave":
        penalty = f"-{value} ATK" if value else "no penalty"
        return text.line("ability_cleave", penalty=penalty, turns=turns)
    if ab.kind == "coat":
        return text.line("ability_coat", charges=charges, damage=value, turns=turns)
    return text.line("ability_dual_strike", bonus=value, turns=turns)


def sheet_lines(game: Game, text: Text) -> list[str]:
    """The character sheet (`c`): attributes, derived numbers, kit, and what the class can do."""
    hero = game.view().hero
    c = game.data.classes[game.player.class_id]
    ability = hero.ability
    state = (
        f"unlocks at Rank {ability.unlock_rank}"
        if not ability.unlocked
        else "ready"
        if ability.ready
        else f"{ability.cooldown_turns} turns to go"
    )
    lines = [
        f"{hero.name} the {hero.class_name}".ljust(SHEET_WIDTH - len(f"Rank {hero.rank}"))
        + f"Rank {hero.rank}",
        f"HP {hero.hp}/{hero.max_hp}",
        f"STR {c.strength} ({modifier(c.strength):+d})   "
        f"DEX {c.dexterity} ({modifier(c.dexterity):+d})",
        f"ATK {hero.atk:+d}   DEF {hero.defense}   DR {hero.dr}   DMG {hero.damage}",
        "",
        f"Main hand   {hero.weapon}",
        f"Off hand    {hero.offhand or '(empty)'}",
        f"Head        {hero.head}",
        f"Body        {hero.body}  {hero.armor_dur}/{hero.armor_max}",
    ]
    if hero.offhand_attack:
        lines.append(f"Off-hand attack: {hero.offhand_attack}")
    lines += ["", text.line(f"signature_{hero.signature}"), ""]
    lines += [f"Ability: {ability.name} ({state})", _ability_text(game, text)]
    return lines
