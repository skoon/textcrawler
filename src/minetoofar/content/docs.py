"""Documents found on the floor (data/text/docs.toml): flavor memos, coupons, map fragments."""

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources

KINDS = ("memo", "coupon", "map")
NAMES = {"memo": "Memo", "coupon": "Coupon", "map": "Map fragment"}


class DocError(ValueError):
    pass


@dataclass(frozen=True)
class DocBook:
    texts: dict[str, tuple[str, ...]]

    def text(self, kind: str, index: int) -> str:
        return self.texts[kind][index]


def parse_docs(text: str) -> DocBook:
    raw = tomllib.loads(text)
    if set(raw) != set(KINDS):
        raise DocError(f"docs.toml needs exactly {KINDS}, got {sorted(raw)}")
    texts: dict[str, tuple[str, ...]] = {}
    for kind in KINDS:
        entries = raw[kind]
        if not isinstance(entries, list) or not entries:
            raise DocError(f"{kind} must be a non-empty list of strings")
        if not all(isinstance(e, str) and e for e in entries):
            raise DocError(f"{kind} must hold non-empty strings")
        texts[kind] = tuple(entries)
    return DocBook(texts)


@cache
def load_docs() -> DocBook:
    base = resources.files("minetoofar").joinpath("data", "text")
    return parse_docs(base.joinpath("docs.toml").read_text("utf-8"))
