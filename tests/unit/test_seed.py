import pytest

from minetoofar.core.rng import Rng
from minetoofar.core.seed import GEN_VERSION, Seed, SeedError, seed_text_from_entropy


def test_canonical_form_ignores_case_spaces_and_hyphens() -> None:
    assert Seed.parse("brass-lamp-42").canonical == "BRASSLAMP42"
    assert Seed.parse(" Brass Lamp 42 ").canonical == "BRASSLAMP42"


@pytest.mark.parametrize("bad", ["", "   ", "---", "café", "a_b", "a.b", "x" * 33, "a:b:c"])
def test_invalid_seeds_are_rejected(bad: str) -> None:
    with pytest.raises(SeedError):
        Seed.parse(bad)


def test_master64_matches_reference_vector() -> None:
    assert Seed.parse("BRASSLAMP42").master64 == 0x7867809C6AD657AF


def test_equivalent_spellings_share_master64() -> None:
    assert Seed.parse("brass-lamp-42").master64 == Seed.parse("BRASSLAMP42").master64


def test_root_rng_starts_at_master64() -> None:
    seed = Seed.parse("BRASSLAMP42")
    assert seed.rng().identity == seed.master64
    assert isinstance(seed.rng(), Rng)


def test_share_code_carries_generator_version() -> None:
    assert Seed.parse("brass-lamp-42").share_code == f"{GEN_VERSION}:BRASSLAMP42"


def test_parse_accepts_matching_share_code() -> None:
    assert Seed.parse(f"{GEN_VERSION}:brass-lamp-42").canonical == "BRASSLAMP42"


def test_parse_refuses_other_generator_version() -> None:
    with pytest.raises(SeedError, match="generator version"):
        Seed.parse(f"{GEN_VERSION + 1}:BRASSLAMP42")


def test_parse_refuses_non_numeric_version() -> None:
    with pytest.raises(SeedError):
        Seed.parse("v1:BRASSLAMP42")


def test_display_groups_by_four() -> None:
    assert Seed.parse("BRASSLAMP42").display == "BRAS-SLAM-P42"


def test_entropy_to_seed_text_uses_60_bits_of_crockford() -> None:
    assert seed_text_from_entropy(bytes(8)) == "000000000000"
    assert seed_text_from_entropy(b"\xff" * 8) == "ZZZZZZZZZZZZ"
    assert seed_text_from_entropy(bytes(7) + b"\x01") == "000000000001"


def test_entropy_needs_eight_bytes() -> None:
    with pytest.raises(ValueError):
        seed_text_from_entropy(b"\x00" * 7)
