"""Reference vectors come from GDD 10.3; they are the tiebreaker for the implementation."""

import pytest

from minetoofar.core.rng import Rng

M64 = (1 << 64) - 1
BRASS_MASTER = 0x7867809C6AD657AF  # master64("BRASSLAMP42"), see test_seed


def draws(rng: Rng, count: int) -> list[int]:
    return [rng.next_u64() for _ in range(count)]


def test_splitmix64_seed_zero_matches_reference_vector() -> None:
    assert draws(Rng(0), 3) == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]


def test_derived_stream_matches_reference_vector() -> None:
    stream = Rng(BRASS_MASTER).derive("level", 3, "layout", 0)
    assert stream.identity == 0x296105EAC18A7DE6
    assert draws(stream, 3) == [0xB08EF064D634C4B3, 0x5EC888633491CA2E, 0x9027C51723EEC10B]


def test_below_matches_reference_vector() -> None:
    stream = Rng(BRASS_MASTER).derive("level", 3, "layout", 0)
    assert [stream.below(100) for _ in range(6)] == [79, 34, 95, 4, 93, 39]


def test_derive_depends_on_identity_not_cursor() -> None:
    fresh = Rng(BRASS_MASTER)
    used = Rng(BRASS_MASTER)
    draws(used, 50)
    assert fresh.derive("spawns").identity == used.derive("spawns").identity


def test_derive_separates_labels() -> None:
    root = Rng(BRASS_MASTER)
    assert root.derive("a").identity != root.derive("b").identity
    assert root.derive("ab", "c").identity != root.derive("a", "bc").identity
    assert root.derive("level", 1).identity != root.derive("level", 2).identity


def test_derive_rejects_non_ascii_label() -> None:
    with pytest.raises(UnicodeEncodeError):
        Rng(1).derive("café")


def test_state_round_trips() -> None:
    a = Rng(12345)
    draws(a, 7)
    b = Rng(a.state)
    assert draws(a, 5) == draws(b, 5)


def test_below_rejects_biased_draws() -> None:
    rng = Rng(0)
    seq = iter([M64, 5])  # for n=3 only 2**64-1 is rejected (2**64 % 3 == 1)
    rng.next_u64 = lambda: next(seq)  # type: ignore[method-assign]
    assert rng.below(3) == 5 % 3


def test_below_rejects_non_positive_bound() -> None:
    with pytest.raises(ValueError):
        Rng(1).below(0)


def test_randrange_is_half_open() -> None:
    rng = Rng(99)
    values = {rng.randrange(5, 8) for _ in range(200)}
    assert values == {5, 6, 7}


def test_randrange_rejects_empty_range() -> None:
    with pytest.raises(ValueError):
        Rng(1).randrange(4, 4)


def test_chance_extremes() -> None:
    rng = Rng(7)
    assert all(rng.chance(100, 100) for _ in range(20))
    assert not any(rng.chance(0, 100) for _ in range(20))


def test_dice_stays_in_range() -> None:
    rng = Rng(3)
    rolls = [rng.dice(2, 6) for _ in range(300)]
    assert min(rolls) >= 2 and max(rolls) <= 12


def test_pick_is_deterministic_and_rejects_empty() -> None:
    items = ["a", "b", "c", "d"]
    assert Rng(5).pick(items) == Rng(5).pick(items)
    with pytest.raises(ValueError):
        Rng(5).pick([])


def test_weighted_respects_weights() -> None:
    rng = Rng(11)
    picks = [rng.weighted([("never", 0), ("always", 5)]) for _ in range(50)]
    assert set(picks) == {"always"}


def test_weighted_rejects_zero_total_and_negative() -> None:
    with pytest.raises(ValueError):
        Rng(1).weighted([("a", 0)])
    with pytest.raises(ValueError):
        Rng(1).weighted([("a", 3), ("b", -1)])


def test_shuffle_is_fisher_yates_descending() -> None:
    expected = list(range(10))
    ref = Rng(2024)
    for i in range(len(expected) - 1, 0, -1):
        j = ref.below(i + 1)
        expected[i], expected[j] = expected[j], expected[i]
    actual = list(range(10))
    Rng(2024).shuffle(actual)
    assert actual == expected
    assert sorted(actual) == list(range(10))
