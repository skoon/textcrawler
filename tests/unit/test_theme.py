from minetoofar.content.balance import LEVELS
from minetoofar.core.seed import Seed
from minetoofar.gen.theme import HUMANS, MOODS, Theme, generate_theme


def themes(count: int) -> list[Theme]:
    return [
        generate_theme(Seed.parse(f"THEME{i:04d}"), level)
        for i in range(count)
        for level in range(1, LEVELS + 1)
    ]


def test_a_theme_depends_only_on_the_seed_and_level() -> None:
    a = generate_theme(Seed.parse("BRASSLAMP42"), 3)
    assert a == generate_theme(Seed.parse("BRASSLAMP42"), 3)
    assert a.sha256 == generate_theme(Seed.parse("brass-lamp-42"), 3).sha256
    assert a != generate_theme(Seed.parse("BRASSLAMP42"), 4)


def test_about_three_levels_in_ten_are_graveyards() -> None:
    sample = themes(200)  # 1000 levels
    graves = sum(t.graveyard for t in sample) * 100 // len(sample)
    assert 24 <= graves <= 36, graves


def test_the_rogue_human_is_grimsby_or_vane_about_evenly() -> None:
    sample = themes(200)
    grimsby = sum(t.human == "foreman_grimsby" for t in sample) * 100 // len(sample)
    assert {t.human for t in sample} == set(HUMANS) and 44 <= grimsby <= 56, grimsby


def test_every_mood_turns_up() -> None:
    assert {t.mood for t in themes(100)} == set(MOODS)


def test_the_dump_is_canonical_text() -> None:
    t = generate_theme(Seed.parse("BRASSLAMP42"), 2)
    lines = t.dump().splitlines()
    assert lines[:3] == ["AMTF-THEME", "seed BRASSLAMP42", "level 2"]
    assert lines[3] == f"graveyard {int(t.graveyard)}"
    assert lines[4:6] == [f"human {t.human}", f"mood {t.mood}"]
    assert lines[6] == f"tic_roll {t.tic_roll}" and t.dump().endswith("\n") and t.dump().isascii()


def test_the_graveyard_roll_has_its_own_stream() -> None:
    # the stream is level/N/theme: asking for it by name must reproduce the first draw
    seed = Seed.parse("BRASSLAMP42")
    rng = seed.rng().derive("level", 3, "theme")
    assert generate_theme(seed, 3).graveyard == rng.chance(30, 100)
