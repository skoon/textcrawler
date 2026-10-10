"""The playable screen with the other classes: abilities, the sheet, sensing, and traps."""

from textual.pilot import Pilot

from minetoofar.core.geometry import Pos
from minetoofar.core.rng import Rng
from minetoofar.sim.traps import Trap
from minetoofar.ui.game_app import SENSED, GameApp, SheetScreen
from minetoofar.ui.mapview import MapView
from tests.helpers import MINER, ScriptedRng, make_game
from tests.ui.test_game_app import rows, run_app, text

HALL = ["#" * 14, "#<" + "." * 11 + "#", "#" * 14]
WALLED = ["#" * 12, "#<..#......#", "#" * 12]
SPRING = "spring_trap"


def on(
    game: object, body: object, glyphs: str = "unicode", size: tuple[int, int] = (80, 24)
) -> None:
    run_app(GameApp(game, glyphs), size, body)  # type: ignore[arg-type]


# -- abilities ---------------------------------------------------------------------------------


def test_the_ability_key_uses_it_and_the_panel_shows_the_cooldown() -> None:
    game = make_game(HALL, rank=3, class_id="rogue")

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert "[a] Poison Blades  rdy" in text(app, "#status")
        await pilot.press("a")
        assert app.text.line("ability_used", name="Poison Blades") in app.messages
        assert "[a] Poison Blades  29t" in text(app, "#status")
        await pilot.press("a")
        assert app.messages[-1] == app.text.line("refused_cooldown")

    on(game, body)


def test_a_locked_ability_says_so_and_costs_nothing() -> None:
    game = make_game(HALL)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert "[a] Cleave  Rk 3" in text(app, "#status")
        await pilot.press("a")
        assert app.messages[-1] == app.text.line("refused_locked") and app.game.ticks == 0

    on(game, body)


def test_a_backstab_is_logged_in_the_corporate_voice() -> None:
    script = ScriptedRng([0, 3, 2, 1])  # natural 1 still hits; d6 4; 2d4 3 + 2
    game = make_game(HALL, [(MINER, (2, 1), "asleep")], script, class_id="rogue")

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l")
        assert app.text.line("you_backstab", target="Shambling Miner", damage=12) in app.messages

    on(game, body)


# -- the character sheet ---------------------------------------------------------------------


def test_c_opens_the_character_sheet_and_any_key_closes_it() -> None:
    game = make_game(HALL, class_id="ranger", rank=3)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("c")
        assert isinstance(app.screen, SheetScreen)
        panel = app.screen.query_one("#sheet")
        shown = str(panel.render())
        assert panel.border_title == "PERSONNEL FILE"
        for line in (
            "Wren the Ranger",
            "STR 13 (+1)   DEX 13 (+1)",
            "Off hand    Hatchet",
            "Off-hand attack: ATK +0  DMG 1d6",
            "Ability: Dual Strike (ready)",
        ):
            assert line in shown, line
        await pilot.press("l")  # the key only closes the sheet: the Ranger does not move
        assert not isinstance(app.screen, SheetScreen) and app.game.pos == Pos(1, 1)
        await pilot.press("l")
        assert app.game.pos == Pos(2, 1)

    on(game, body)


# -- sensing and traps on the map ----------------------------------------------------------


def test_the_rangers_sensed_enemy_is_drawn_through_the_wall_in_cyan() -> None:
    game = make_game(WALLED, [(MINER, (6, 1), "asleep")], Rng(1), class_id="ranger")

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view = app.query_one(MapView)
        char, style = view.row_cells(1)[6]
        assert char == "M" and style == SENSED
        assert "~ Shambling Miner" in text(app, "#status")

    on(game, body)


def test_in_ascii_sensed_enemies_are_question_marks() -> None:
    game = make_game(WALLED, [(MINER, (6, 1), "asleep")], Rng(1), class_id="ranger")

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert app.query_one(MapView).row_cells(1)[6][0] == "?"

    on(game, body, glyphs="ascii")


def test_fighters_do_not_sense() -> None:
    game = make_game(WALLED, [(MINER, (6, 1), "asleep")], Rng(1))

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert app.query_one(MapView).row_cells(1)[6][0] == " "

    on(game, body)


def test_revealed_traps_are_drawn_and_hidden_ones_look_like_floor() -> None:
    game = make_game(HALL, traps=[Trap(Pos(3, 1), SPRING, revealed=True), Trap(Pos(4, 1), SPRING)])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        cells = app.query_one(MapView).row_cells(1)
        assert cells[3][0] == "Δ" and cells[4][0] == "·"
        app.game.traps[0].disarmed = True
        await pilot.press("full_stop")
        assert app.query_one(MapView).row_cells(1)[3][0] == "×"

    on(game, body)


def test_ascii_traps() -> None:
    game = make_game(HALL, traps=[Trap(Pos(3, 1), SPRING, revealed=True)])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        assert app.query_one(MapView).row_cells(1)[3][0] == "^"

    on(game, body, glyphs="ascii")


# -- walking into a known trap -----------------------------------------------------------------


def test_a_rogue_walking_into_a_revealed_trap_is_offered_a_disarm() -> None:
    game = make_game(HALL, class_id="rogue", traps=[Trap(Pos(2, 1), SPRING)])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l")
        assert app.messages[-1] == app.text.line("disarm_prompt", name="Spring Trap")
        assert app.game.pos == Pos(1, 1) and app.game.ticks == 0
        await pilot.press("y")
        assert app.text.line("trap_disarmed", name="Spring Trap") in app.messages
        assert app.game.traps[0].disarmed and app.game.pos == Pos(1, 1)

    on(game, body)


def test_declining_the_disarm_does_nothing() -> None:
    game = make_game(HALL, class_id="rogue", traps=[Trap(Pos(2, 1), SPRING)])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l", "n")
        assert not app.game.traps[0].disarmed and app.game.ticks == 0
        await pilot.press("h")  # the prompt is gone; ordinary keys work (a wall here)
        assert app.messages[-1] == app.text.line("blocked_wall")

    on(game, body)


def test_other_classes_are_asked_before_stepping_on_a_known_trap() -> None:
    trap = Trap(Pos(2, 1), SPRING, revealed=True)
    game = make_game(HALL, rng=ScriptedRng([3]), traps=[trap])  # d6 4 + 2, less the Hard Hat's 2

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l")
        assert app.messages[-1] == app.text.line("step_prompt", name="Spring Trap")
        await pilot.press("n")
        assert app.game.pos == Pos(1, 1) and app.game.player.hp == 30
        await pilot.press("l", "y")
        assert app.game.pos == Pos(2, 1) and app.game.player.hp == 26
        assert app.text.line("trap_triggered", name="Spring Trap", damage=4) in app.messages

    on(game, body)


def test_a_disarmed_trap_is_walked_over_without_a_prompt() -> None:
    game = make_game(HALL, traps=[Trap(Pos(2, 1), SPRING, revealed=True, disarmed=True)])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l")
        assert app.game.pos == Pos(2, 1)

    on(game, body)


def test_running_toward_a_known_trap_says_why_it_stopped() -> None:
    game = make_game(HALL, traps=[Trap(Pos(2, 1), SPRING, revealed=True)])

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("L")
        assert app.messages[-1] == app.text.line("blocked_trap") and app.game.pos == Pos(1, 1)

    on(game, body)


def test_unrelated_prompts_still_work_the_quit_prompt() -> None:
    game = make_game(HALL)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("Q", "y")
        await pilot.pause()
        assert not app.is_running
        assert rows(app) is not None

    on(game, body)
