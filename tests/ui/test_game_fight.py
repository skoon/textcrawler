"""The playable screen in a fight: monsters on the map, the panel, the log, and the death screen."""

import pytest
from textual.pilot import Pilot

from minetoofar.core.geometry import DIRS8, Pos
from minetoofar.core.rng import Rng
from minetoofar.core.seed import Seed, seed_text_from_entropy
from minetoofar.sim.actors import new_monster
from minetoofar.sim.events import SetRank
from minetoofar.sim.game import Game
from minetoofar.ui.game_app import DeathScreen, GameApp, SlipScreen
from minetoofar.ui.mapview import MapView
from tests.helpers import DATA, MINER, ScriptedRng, make_game
from tests.ui.test_game_app import rows, run_app, text

HALL = ["#" * 14, "#<" + "." * 11 + "#", "#" * 14]


def face(n: int) -> int:
    return n - 1


def on_fight(
    game: Game, body: object, size: tuple[int, int] = (80, 24), glyphs: str = "unicode"
) -> None:
    run_app(GameApp(game, glyphs), size, body)  # type: ignore[arg-type]


def test_visible_monsters_are_drawn_and_distant_ones_stay_hidden() -> None:
    game = make_game(HALL, [(MINER, (3, 1), "asleep"), (MINER, (10, 1), "asleep")], Rng(3))

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        row = rows(app)[1]
        assert row[3] == "M" and row[10] == " "

    on_fight(game, body)


def test_the_status_panel_shows_the_fighter_and_whoever_is_nearby() -> None:
    game = make_game(HALL, [(MINER, (3, 1), "asleep")], Rng(3))

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        panel = text(app, "#status")
        assert "Hale the Fighter" in panel and "HP ████████████ 30/30" in panel
        assert "DEF 1  ATK +5  DMG 1d8+3" in panel
        assert "Nearby" in panel and "M Shambling Miner  12/12" in panel

    on_fight(game, body)


def test_a_blow_lands_in_the_log_and_the_panel_follows_the_damage() -> None:
    # player: d20 face 15, d8 face 5 -> 8 damage; Miner wakes and hits: face 15, d6 face 4 -> 3
    script = ScriptedRng([face(15), face(5), face(15), face(4)])
    game = make_game(HALL, [(MINER, (2, 1), "asleep")], script)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l")
        log = app.messages
        assert app.text.line("you_hit", target="Shambling Miner", damage=8) in log
        assert app.text.line("noticed", name="Shambling Miner") in log
        assert app.text.line("they_hit", attacker="Shambling Miner", damage=3) in log
        panel = text(app, "#status")
        assert "27/30" in panel and "Armor 17/18" in panel and "4/12" in panel
        assert app.game.pos == Pos(1, 1)  # attacking does not move the player

    on_fight(game, body)


def test_killing_a_monster_clears_it_from_the_map_and_panel() -> None:
    game = make_game(HALL, [(MINER, (2, 1), "asleep")], ScriptedRng([face(15), face(8)]))
    game.monsters[0].hp = 5

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l")
        assert app.text.line("you_killed", target="Shambling Miner") in app.messages
        assert "M" not in rows(app)[1] and "Nearby" not in text(app, "#status")

    on_fight(game, body)


def test_look_names_a_monster_and_its_health() -> None:
    game = make_game(HALL, [(MINER, (3, 1), "asleep")], Rng(3))

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        view = app.query_one(MapView)
        await pilot.press("x", "l", "l")
        assert view.cursor == Pos(3, 1)
        assert view.border_subtitle == "Shambling Miner 12/12"

    on_fight(game, body)


def test_spotting_a_monster_for_the_first_time_is_logged() -> None:
    game = make_game(HALL, [(MINER, (8, 1), "asleep")], ScriptedRng([5, 5, 5]))

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await pilot.press("l", "l", "l")
        assert app.text.line("spotted", name="Shambling Miner") in app.messages

    on_fight(game, body)


# -- death ---------------------------------------------------------------------------------


def doomed_game(seed: str = "BRASSLAMP42") -> Game:
    """A real level with a hunting Miner beside a one-hit-point Fighter whose luck has run out."""
    game = Game.new(Seed.parse(seed), 1)
    game.monsters.clear()
    for d in DIRS8:
        if game.grid.can_step(game.pos, d):
            pos = game.pos.step(d)
            game.monsters.append(new_monster(DATA, MINER, 1, pos, "hunting", 1))
            break
    game.player.hp, game.player.stubborn_used = 1, True
    return game


async def die(app: GameApp, pilot: Pilot[None]) -> None:
    """Wait until the Fighter dies and has signed the Posthumous Pay Slip."""
    for _ in range(60):
        if isinstance(app.screen, DeathScreen):
            return
        await pilot.press("enter" if isinstance(app.screen, SlipScreen) else "full_stop")
        await pilot.pause()
    raise AssertionError("the Fighter never died")


def test_death_opens_the_incident_report_and_freezes_play() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await die(app, pilot)
        panel = app.screen.query_one("#death")
        assert panel.border_title == "INCIDENT REPORT"
        report = str(panel.render())
        for line in (
            "Associate: Hale (Fighter, Rank 1)",
            "Cause of death: Shambling Miner",
            "Work Order 1 of 5: Light Housekeeping",
            "Seed: 1:BRASSLAMP42",
            "[R] Retry this seed",
        ):
            assert line in report, line
        assert app.text.line("died", killer="Shambling Miner") in app.messages
        await pilot.press("l", "full_stop")  # no command may reach a dead game
        assert app.game.dead and isinstance(app.screen, DeathScreen)

    on_fight(doomed_game(), body)


def test_retry_restarts_the_same_seed_and_level_with_a_fresh_fighter() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await die(app, pilot)
        await pilot.press("r")
        await pilot.pause()
        assert not isinstance(app.screen, DeathScreen)
        game = app.game
        assert not game.dead and game.player.hp == 30 and game.ticks == 0
        assert (game.spec.seed, game.spec.level) == ("BRASSLAMP42", 1)
        assert len(app.messages) == 1 and "Work Order 1" in app.messages[0]
        await pilot.press("full_stop")
        assert app.game.ticks == 100

    on_fight(doomed_game(), body)


def test_new_seed_starts_a_different_mine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("minetoofar.ui.game_app.secrets.token_bytes", lambda n: b"\x01" * n)

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await die(app, pilot)
        await pilot.press("n")
        await pilot.pause()
        want = Seed.parse(seed_text_from_entropy(b"\x01" * 8)).canonical
        assert app.game.spec.seed == want != "BRASSLAMP42"
        assert not app.game.dead and f"1:{want}" in text(app, "#status")

    on_fight(doomed_game(), body)


def test_quit_from_the_report_ends_the_program() -> None:
    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await die(app, pilot)
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running

    on_fight(doomed_game(), body)


def test_retry_keeps_the_starting_rank() -> None:
    game = doomed_game()
    game.submit(SetRank(3))
    game.player.hp, game.player.stubborn_used = 1, True

    async def body(app: GameApp, pilot: Pilot[None]) -> None:
        await die(app, pilot)
        await pilot.press("r")
        await pilot.pause()
        assert app.game.player.rank == 3 and app.game.player.max_hp == 35

    on_fight(game, body)
