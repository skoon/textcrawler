"""The `desk` stage (GDD 5.3, 8.5, 10.4): each check-in's seeded stock and company memo."""

from minetoofar.content.balance import LEVELS, load_balance
from minetoofar.content.desk import load_desk
from minetoofar.content.memos import load_memos
from minetoofar.core.seed import Seed
from minetoofar.gen.desk import generate_desk
from minetoofar.gen.theme import generate_theme
from minetoofar.gen.world import generate_world

SEEDS = [f"GOLD{n:04d}" for n in range(1, 61)]
CATALOG = load_desk()
BOOK = load_memos()
SLOTS = load_balance().checkin.desk_slots


def test_the_desk_is_a_pure_function_of_seed_and_check_in() -> None:
    a = generate_desk(Seed.parse("GOLD0001"), 2)
    assert (
        a == generate_desk(Seed.parse("GOLD0001"), 2)
        and a.sha256 == generate_desk(Seed.parse("GOLD0001"), 2).sha256
    )
    assert a.sha256 != generate_desk(Seed.parse("GOLD0002"), 2).sha256
    assert a.sha256 != generate_desk(Seed.parse("GOLD0001"), 3).sha256


def test_four_items_the_first_a_bundle_and_no_item_twice() -> None:
    for s in SEEDS:
        for level in range(1, LEVELS):
            stock = generate_desk(Seed.parse(s), level).stock
            assert len(stock) == SLOTS and len(set(stock)) == SLOTS
            assert CATALOG[stock[0]].effect == "bundle"
            assert all(CATALOG[k].effect != "bundle" for k in stock[1:])


def test_every_catalog_item_turns_up() -> None:
    seen = {
        k
        for s in SEEDS
        for level in range(1, LEVELS)
        for k in generate_desk(Seed.parse(s), level).stock
    }
    assert seen == set(CATALOG)


def test_the_last_check_in_has_no_desk_and_no_memo() -> None:
    d = generate_desk(Seed.parse("GOLD0001"), LEVELS)
    assert d.stock == () and d.memo is None


def test_the_memo_announces_whether_the_next_level_is_a_graveyard() -> None:
    premium = load_balance().economy.hazard_premium
    graves = plain = 0
    for s in SEEDS:
        for level in range(1, LEVELS):
            seed = Seed.parse(s)
            text = "\n".join(generate_desk(seed, level).memo.lines)  # type: ignore[union-attr]
            if generate_theme(seed, level + 1).graveyard:
                graves += 1
                assert f"Level {level + 1}" in text and f"{premium}g" in text and "Memorial" in text
            else:
                plain += 1
                assert f"Level {level + 1}" in text and "No Hazard Premium" in text
    assert graves > 20 and plain > 20


def test_a_memo_is_a_sender_a_subject_and_a_handful_of_lines_from_the_templates() -> None:
    for s in SEEDS[:20]:
        memo = generate_desk(Seed.parse(s), 2).memo
        assert memo is not None
        assert memo.sender in BOOK.senders
        assert memo.subject.startswith("RE: ") and any(x in memo.subject for x in BOOK.subjects)
        body = "\n".join(memo.lines)
        assert any(o in body for o in BOOK.openers) and any(r in body for r in BOOK.reminders)
        assert any(sig in body for sig in BOOK.signoffs)
        assert any(line in body for pair in BOOK.policies for line in pair)


def policy_of(seed: str, level: int) -> tuple[int, int]:
    body = "\n".join(generate_desk(Seed.parse(seed), level).memo.lines)  # type: ignore[union-attr]
    for i, pair in enumerate(BOOK.policies):
        for side, line in enumerate(pair):
            if line in body:
                return i, side
    raise AssertionError("no policy in the memo")


def test_a_later_memo_often_contradicts_the_one_before() -> None:
    flips = same = 0
    for s in SEEDS:
        for level in range(1, LEVELS - 1):
            (a, sa), (b, sb) = policy_of(s, level), policy_of(s, level + 1)
            if a == b:
                flips += sa != sb
                same += sa == sb
    assert flips >= 15 and flips > same  # the company reverses itself


def test_the_dump_is_canonical_text() -> None:
    world = generate_world(Seed.parse("GOLD0001"), 2)
    lines = world.desk.dump().splitlines()
    assert lines[:3] == ["AMTF-DESK", "seed GOLD0001", "level 2"]
    assert world.stage("desk") is world.desk and world.desk.dump().isascii()
    assert world.desk.dump().endswith("\n")
