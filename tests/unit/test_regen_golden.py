"""The generator freeze (GDD 10.7): once a version ships, its goldens may grow but never change."""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

TOOL = Path(__file__).resolve().parents[2] / "tools" / "regen_golden.py"


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("regen_golden", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def manifest(version: int = 1, **hashes: str) -> dict[str, Any]:
    """A manifest with one seed whose level-1 stage hashes are `hashes`."""
    return {"gen_version": version, "full_dumps": [], "seeds": {"GOLD0001": {"1": hashes}}}


def test_nothing_changed_means_nothing_to_report() -> None:
    assert (
        tool.changed_hashes(manifest(layout="a", theme="b"), manifest(layout="a", theme="b")) == []
    )


def test_a_changed_hash_is_named_by_seed_level_and_stage() -> None:
    old, new = manifest(layout="a", theme="b"), manifest(layout="a", theme="X")
    assert tool.changed_hashes(old, new) == ["GOLD0001 L1 theme"]


def test_new_seeds_and_stages_are_not_changes() -> None:
    old = manifest(layout="a")
    new = manifest(layout="a", theme="b")
    new["seeds"]["GOLD0002"] = {"1": {"layout": "c"}}
    assert tool.changed_hashes(old, new) == []


def test_the_same_version_may_not_change_a_hash() -> None:
    with pytest.raises(tool.FrozenGenerator, match="GOLD0001 L1 layout"):
        tool.check_freeze(manifest(1, layout="a"), manifest(1, layout="Z"))


def test_a_bumped_version_may_change_anything() -> None:
    tool.check_freeze(manifest(1, layout="a"), manifest(2, layout="Z"))


def test_the_same_version_may_add_to_the_goldens() -> None:
    new = manifest(1, layout="a")
    new["seeds"]["GOLD0002"] = {"1": {"layout": "c"}}
    tool.check_freeze(manifest(1, layout="a"), new)


def test_a_first_manifest_has_nothing_to_protect() -> None:
    tool.check_freeze(None, manifest(1, layout="a"))


def test_the_message_says_how_to_proceed() -> None:
    with pytest.raises(tool.FrozenGenerator, match="GEN_VERSION"):
        tool.check_freeze(manifest(1, layout="a"), manifest(1, layout="Z"))


def test_a_long_list_of_changes_is_cut_short() -> None:
    old = manifest(**{f"s{i}": "a" for i in range(30)})
    new = manifest(**{f"s{i}": "b" for i in range(30)})
    with pytest.raises(tool.FrozenGenerator, match=r"and 20 more"):
        tool.check_freeze(old, new)
