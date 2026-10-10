from minetoofar.content.text import load_text
from minetoofar.core.geometry import Pos
from minetoofar.sim.events import UseAbility, Wait
from minetoofar.sim.views import MonsterView
from minetoofar.ui.glyphs import ASCII, UNICODE
from minetoofar.ui.panels import nearby_lines, sheet_lines, status_lines
from tests.helpers import MINER, make_game

WIDTH = 24  # the status panel's text width on any screen


def lines(rows: list[str]) -> list[str]:
    return status_lines(make_game(rows).view(), UNICODE, "1:TEST")


def test_fresh_fighter_panel() -> None:
    out = lines(["#####", "#<..#", "#####"])
    assert out[0] == "Hale the Fighter    Rk1"
    assert out[1] == "HP ████████████ 30/30"
    assert out[2] == "DEF 1  ATK +5  DMG 1d8+3"
    assert out[3] == "Armor 18/18"
    assert out[4] == "Light: Hard Hat (4)"
    assert out[-2:] == ["Turn 0", "Seed 1:TEST"]


def test_every_line_fits_the_panel() -> None:
    game = make_game(["#######", "#<....#", "#######"], [(MINER, (3, 1), "idle")])
    game.player.hp, game.player.body_dur = 7, 0
    game.submit(Wait())
    for line in status_lines(game.view(), UNICODE, "1:ABCDEFGHJKMNPQRSTVWXYZ0123456789"):
        assert len(line) <= WIDTH or line.startswith("Seed"), line


def test_hp_bar_and_numbers_follow_damage_and_ascii_set() -> None:
    game = make_game(["#####", "#<..#", "#####"])
    game.player.hp = 15
    out = status_lines(game.view(), ASCII, "1:TEST")
    assert out[1] == "HP ######------ 15/30"


def test_broken_armor_is_called_out() -> None:
    game = make_game(["#####", "#<..#", "#####"])
    game.player.body_dur = 0
    assert status_lines(game.view(), UNICODE, "1:T")[3] == "Armor 0/18 BROKEN"


def test_nearby_lists_visible_monsters_nearest_first_with_hp() -> None:
    near = MonsterView(2, "shambling_miner", "Shambling Miner", Pos(3, 1), 12, 12)
    far = MonsterView(1, "shambling_miner", "Shambling Miner", Pos(5, 1), 7, 12)
    out = nearby_lines((far, near), Pos(1, 1), UNICODE)
    assert out == ["M Shambling Miner  12/12", "M Shambling Miner   7/12"]  # HP right-aligned
    assert all(len(line) <= WIDTH for line in out)


def test_nearby_shows_at_most_five_and_a_header_in_the_panel() -> None:
    game = make_game(
        ["##########", "#<.......#", "##########"],
        [(MINER, (x, 1), "idle") for x in (2, 3, 4, 5)],
    )
    out = status_lines(game.view(), UNICODE, "1:T")
    assert "Nearby" in out
    assert sum(line.startswith("M ") for line in out) == 4


def test_ability_line_shows_locked_ready_and_cooling_down() -> None:
    locked = status_lines(make_game(["#####", "#<..#", "#####"]).view(), UNICODE, "1:T")
    assert "[a] Cleave  Rk 3" in locked
    ready = status_lines(make_game(["#####", "#<..#", "#####"], rank=3).view(), UNICODE, "1:T")
    assert "[a] Cleave  rdy" in ready


def test_ability_line_counts_cooldown_turns() -> None:
    game = make_game(["#####", "#<..#", "#####"], rank=3, class_id="rogue")
    game.submit(UseAbility())
    line = [x for x in status_lines(game.view(), UNICODE, "1:T") if x.startswith("[a]")][0]
    assert line == "[a] Poison Blades  29t"  # used at 0, 100 ticks gone of 3000
    assert len(line) <= WIDTH


def test_every_class_ability_line_fits() -> None:
    for class_id in ("fighter", "rogue", "ranger"):
        for rank in (1, 3):
            game = make_game(["#####", "#<..#", "#####"], rank=rank, class_id=class_id)
            assert all(len(x) <= WIDTH for x in status_lines(game.view(), UNICODE, "1:T")), class_id


def test_the_class_name_follows_the_character() -> None:
    game = make_game(["#####", "#<..#", "#####"], class_id="ranger")
    assert status_lines(game.view(), UNICODE, "1:T")[0] == "Wren the Ranger     Rk1"


def test_sensed_enemies_are_listed_after_the_visible_ones_without_health() -> None:
    game = make_game(
        ["############", "#<..#......#", "############"],
        [(MINER, (6, 1), "asleep"), (MINER, (2, 1), "asleep")],
        class_id="ranger",
    )
    out = status_lines(game.view(), UNICODE, "1:T")
    near = out[out.index("Nearby") + 1 :]
    assert near[0].startswith("M Shambling Miner") and near[0].endswith("12/12")
    assert near[1] == "~ Shambling Miner"


TEXT = load_text()


def sheet(class_id: str, rank: int = 1) -> list[str]:
    game = make_game(["#####", "#<..#", "#####"], rank=rank, class_id=class_id)
    return sheet_lines(game, TEXT)


def test_the_fighters_sheet_has_every_gdd_number() -> None:
    out = sheet("fighter")
    assert out[0] == "Hale the Fighter" + " " * 22 + "Rank 1"
    assert "HP 30/30" in out
    assert "STR 16 (+3)   DEX 10 (+0)" in out
    assert "ATK +5   DEF 1   DR 2   DMG 1d8+3" in out
    assert "Main hand   Company Pickaxe" in out and "Off hand    Sheet-Metal Shield" in out
    assert "Head        Hard Hat" in out and "Body        Boiler Suit  18/18" in out
    assert TEXT.line("signature_stubborn") in out


def test_the_rogues_sheet_shows_finesse_and_an_empty_off_hand() -> None:
    out = sheet("rogue")
    assert "STR 10 (+0)   DEX 16 (+3)" in out
    assert "ATK +5   DEF 5   DR 0   DMG 1d6+3" in out
    assert "Off hand    (empty)" in out and TEXT.line("signature_backstab") in out


def test_the_rangers_sheet_lists_the_off_hand_attack() -> None:
    out = sheet("ranger")
    assert "ATK +3   DEF 2   DR 1   DMG 1d6+1" in out
    assert "Off hand    Hatchet" in out and "Off-hand attack: ATK -1  DMG 1d6" in out


def test_the_sheet_describes_the_ability_at_the_current_rank() -> None:
    cleave = TEXT.line("ability_cleave", penalty="-2 ATK", turns=4)
    assert cleave in sheet("fighter", rank=3)
    assert TEXT.line("ability_cleave", penalty="no penalty", turns=3) in sheet("fighter", rank=5)
    assert TEXT.line("ability_coat", charges=6, damage=3, turns=30) in sheet("rogue", rank=5)
    assert TEXT.line("ability_dual_strike", bonus=2, turns=3) in sheet("ranger", rank=5)


def test_the_sheet_says_when_the_ability_is_locked_ready_or_cooling() -> None:
    assert "Ability: Cleave (unlocks at Rank 3)" in sheet("fighter", rank=1)
    assert "Ability: Cleave (ready)" in sheet("fighter", rank=3)
