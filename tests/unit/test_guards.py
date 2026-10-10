"""Enforce the determinism rules and package boundaries from the Implementation Plan 2.1."""

from pathlib import Path

import pytest

from tests.guards import boundary_violations, determinism_violations

SRC = Path(__file__).resolve().parents[2] / "src" / "minetoofar"
PURE_PACKAGES = ("core", "gen", "sim")


@pytest.mark.parametrize(
    ("source", "needle"),
    [
        ("import random", "random"),
        ("from time import time", "time"),
        ("import datetime", "datetime"),
        ("import os", "os"),
        ("import uuid", "uuid"),
        ("x = 1.5", "float"),
        ("x = a / b", "division"),
        ("x /= 2", "division"),
        ("x = hash(a)", "hash"),
        ("x = id(a)", "id"),
        ("x = float(a)", "float"),
    ],
)
def test_checker_flags_forbidden_constructs(source: str, needle: str) -> None:
    found = determinism_violations(source)
    assert any(needle in v for v in found), found


def test_checker_accepts_integer_code() -> None:
    assert determinism_violations("x = (a + b) // 2\ny = a % 3\nz = 10 ** 2\n") == []


def test_boundary_checker_flags_upward_imports() -> None:
    assert boundary_violations("core", "from minetoofar.gen import layout")
    assert boundary_violations("gen", "import minetoofar.ui.app")
    assert boundary_violations("core", "import json") == []
    assert boundary_violations("gen", "from minetoofar.core.rng import Rng") == []


@pytest.mark.parametrize("package", PURE_PACKAGES)
def test_pure_packages_obey_determinism_rules(package: str) -> None:
    for path in sorted((SRC / package).glob("*.py")):
        assert determinism_violations(path.read_text("utf-8")) == [], path


@pytest.mark.parametrize("package", ["core", "content", "gen", "sim", "persist"])
def test_packages_respect_import_boundaries(package: str) -> None:
    for path in sorted((SRC / package).glob("*.py")):
        assert boundary_violations(package, path.read_text("utf-8")) == [], path


def test_no_file_relative_reads_outside_ui_and_persist() -> None:
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).parts
        if rel[0] in ("ui", "persist"):
            continue
        assert "__file__" not in path.read_text("utf-8"), path
