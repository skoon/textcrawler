import pytest

from minetoofar.content.speech import SpeechError, load_speech, parse_speech, render_lines
from minetoofar.core.rng import Rng

BOOK = load_speech()
MOODS = ("cheerful", "petty", "grandiose")
GOOD = """
[foreman_grimsby]
tics = ["tic"]
[foreman_grimsby.on_sight]
template = "{a}!"
[foreman_grimsby.on_sight.a]
cheerful = ["A1", "A2"]
petty = ["P1"]
grandiose = ["G1"]
[foreman_grimsby.on_hit]
template = "hit"
[foreman_grimsby.on_hurt]
template = "hurt"
[foreman_grimsby.on_death]
template = "dead"
[prospector_vane]
tics = ["tic"]
[prospector_vane.on_sight]
template = "sight"
[prospector_vane.on_hit]
template = "hit"
[prospector_vane.on_hurt]
template = "hurt"
[prospector_vane.on_flee]
template = "flee"
[prospector_vane.on_death]
template = "dead"
"""


def test_the_shipped_book_has_every_event_for_both_humans() -> None:
    grimsby = set(BOOK.events["foreman_grimsby"])
    vane = set(BOOK.events["prospector_vane"])
    assert grimsby == {"on_sight", "on_hit", "on_hurt", "on_death"}  # Grimsby never flees
    assert vane == grimsby | {"on_flee"}
    assert all(BOOK.tics[k] for k in BOOK.tics)


def test_the_gdd_example_greetings_are_in_the_book() -> None:
    sight = BOOK.events["foreman_grimsby"]["on_sight"]
    assert sight.template == "{greet}, {epithet}! {shift_line} {order}"
    assert "Clock in" in sight.slots["greet"]["cheerful"]
    assert "Boys, put in some overtime!" in sight.slots["order"]["cheerful"]
    vane = BOOK.events["prospector_vane"]["on_sight"]
    assert "Fresh claim-jumper!" in vane.slots["greet"]["cheerful"]


@pytest.mark.parametrize("kind", ["foreman_grimsby", "prospector_vane"])
@pytest.mark.parametrize("mood", MOODS)
def test_every_mood_renders_every_line_without_leftover_braces(kind: str, mood: str) -> None:
    for seed in range(20):
        lines = render_lines(BOOK, kind, mood, tic_roll=seed, rng=Rng(seed), tic_one_in=3)
        assert set(lines) == set(BOOK.events[kind])
        for text in lines.values():
            assert text and "{" not in text and "}" not in text and len(text) < 160


def test_rendering_is_a_pure_function_of_its_inputs() -> None:
    a = render_lines(BOOK, "foreman_grimsby", "petty", 7, Rng(5), 3)
    b = render_lines(BOOK, "foreman_grimsby", "petty", 7, Rng(5), 3)
    assert a == b and a != render_lines(BOOK, "foreman_grimsby", "petty", 7, Rng(6), 3)


def test_the_moods_use_their_own_words() -> None:
    petty = {
        render_lines(BOOK, "foreman_grimsby", "petty", 0, Rng(s), 10**9)["on_hit"]
        for s in range(30)
    }
    assert petty <= {
        f"{h} {f}"
        for h in BOOK.events["foreman_grimsby"]["on_hit"].slots["hit"]["petty"]
        for f in BOOK.events["foreman_grimsby"]["on_hit"].slots["follow"]["petty"]
    }


def test_the_tic_is_appended_to_about_one_line_in_three() -> None:
    tic = BOOK.tics["prospector_vane"][2 % len(BOOK.tics["prospector_vane"])]
    tagged = total = 0
    for seed in range(300):
        for text in render_lines(BOOK, "prospector_vane", "cheerful", 2, Rng(seed), 3).values():
            total += 1
            tagged += text.endswith(tic)
    assert 25 <= tagged * 100 // total <= 42


def test_a_tic_every_line_when_the_odds_are_one_in_one() -> None:
    tic = BOOK.tics["foreman_grimsby"][0]
    lines = render_lines(BOOK, "foreman_grimsby", "cheerful", 0, Rng(1), 1)
    assert all(text.endswith(tic) for text in lines.values())


def test_a_minimal_book_parses() -> None:
    book = parse_speech(GOOD)
    lines = render_lines(book, "foreman_grimsby", "petty", 0, Rng(1), 10**9)
    assert lines["on_sight"] == "P1!"


@pytest.mark.parametrize(
    ("old", "new", "word"),
    [
        ('[foreman_grimsby.on_hurt]\ntemplate = "hurt"\n', "", "on_hurt"),
        ('[prospector_vane.on_flee]\ntemplate = "flee"\n', "", "on_flee"),
        ('petty = ["P1"]\n', "", "petty"),
        ('petty = ["P1"]', "petty = []", "petty"),
        ('template = "{a}!"', 'template = "{b}!"', "'b'"),
        (
            'tics = ["tic"]\n[foreman_grimsby.on_sight]',
            "tics = []\n[foreman_grimsby.on_sight]",
            "tics",
        ),
        (
            '[foreman_grimsby.on_hit]\ntemplate = "hit"',
            '[foreman_grimsby.on_hit]\ntemplate = "hit"\n'
            '[foreman_grimsby.on_dance]\ntemplate = "x"',
            "on_dance",
        ),
    ],
)
def test_malformed_books_are_rejected(old: str, new: str, word: str) -> None:
    with pytest.raises(SpeechError, match=word):
        parse_speech(GOOD.replace(old, new, 1))
