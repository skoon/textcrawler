"""AST checkers behind tests/unit/test_guards.py."""

import ast

BANNED_IMPORTS = {"random", "time", "datetime", "uuid", "os", "secrets"}
BANNED_CALLS = {"hash", "id", "float"}

# What each package may import from this project (Implementation Plan 2.1).
ALLOWED = {
    "core": set(),
    "content": {"core"},
    "gen": {"core", "content"},
    "sim": {"core", "content", "gen"},
    "persist": {"core", "content", "gen", "sim"},
}


def determinism_violations(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [
                f"import {a.name}" for a in node.names if a.name.split(".")[0] in BANNED_IMPORTS
            ]
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in BANNED_IMPORTS:
                found.append(f"import from {node.module}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            found.append(f"float literal {node.value}")
        elif isinstance(node, ast.Div):
            found.append("true division")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BANNED_CALLS:
                found.append(f"call to {node.func.id}()")
    return found


def boundary_violations(package: str, source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for name in names:
            parts = name.split(".")
            if parts[0] == "minetoofar" and len(parts) > 1:
                target = parts[1]
                if target != package and target not in ALLOWED[package]:
                    found.append(f"{package} must not import {name}")
    return found
