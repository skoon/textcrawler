"""Strict TOML-table-to-dataclass loading: integers and strings only, no extra or missing keys."""

from typing import Any, get_type_hints


class DataError(ValueError):
    pass


def _value(kind: Any, value: Any, where: str) -> Any:
    if kind is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise DataError(f"{where} must be an integer, got {value!r}")
        return value
    if kind is str:
        if not isinstance(value, str):
            raise DataError(f"{where} must be a string, got {value!r}")
        return value
    if kind == tuple[int, ...]:
        if not isinstance(value, list):
            raise DataError(f"{where} must be a list of integers, got {value!r}")
        return tuple(_value(int, v, f"{where}[{i}]") for i, v in enumerate(value))
    raise TypeError(f"unsupported field type {kind!r} at {where}")


def build[T](cls: type[T], table: object, where: str) -> T:
    """Make a `cls` (a dataclass) from a TOML table, rejecting anything not spelled out."""
    if not isinstance(table, dict):
        raise DataError(f"{where} must be a table")
    hints = get_type_hints(cls)
    unknown = sorted(set(table) - set(hints))
    if unknown:
        raise DataError(f"{where}: unknown keys {unknown}")
    missing = [name for name in hints if name not in table]
    if missing:
        raise DataError(f"{where}: missing keys {missing}")
    return cls(
        **{name: _value(kind, table[name], f"{where}.{name}") for name, kind in hints.items()}
    )


def tables(raw: object, where: str) -> dict[str, object]:
    """A table of named sub-tables, e.g. every `[weapon.<id>]`."""
    if not isinstance(raw, dict):
        raise DataError(f"{where} must be a table of tables")
    return raw
