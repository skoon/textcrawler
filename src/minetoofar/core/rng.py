"""SplitMix64 PRNG and by-identity stream derivation (GDD 10.3). Integers only."""

import hashlib
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")

_M64 = (1 << 64) - 1
_GAMMA = 0x9E3779B97F4A7C15


def derive_state(parent: int, *labels: str | int) -> int:
    """Initial state of the child stream named by `labels` under stream identity `parent`."""
    h = hashlib.sha256()
    h.update(parent.to_bytes(8, "big"))
    for label in labels:
        raw = str(label).encode("ascii")
        h.update(bytes([len(raw)]))
        h.update(raw)
    return int.from_bytes(h.digest()[:8], "big")


class Rng:
    """One stream. `identity` never changes; `state` advances with every draw."""

    def __init__(self, state: int) -> None:
        self.identity = state & _M64
        self.state = self.identity

    def next_u64(self) -> int:
        self.state = (self.state + _GAMMA) & _M64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _M64
        return z ^ (z >> 31)

    def derive(self, *labels: str | int) -> "Rng":
        """Fork by identity, never by cursor, so extra draws elsewhere cannot shift this stream."""
        return Rng(derive_state(self.identity, *labels))

    def below(self, n: int) -> int:
        """Unbiased integer in [0, n) by rejection."""
        if n <= 0:
            raise ValueError(f"below() needs n > 0, got {n}")
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            x = self.next_u64()
            if x < limit:
                return x % n

    def randrange(self, lo: int, hi: int) -> int:
        """Integer in [lo, hi)."""
        if hi <= lo:
            raise ValueError(f"empty range [{lo}, {hi})")
        return lo + self.below(hi - lo)

    def chance(self, num: int, den: int) -> bool:
        return self.below(den) < num

    def dice(self, count: int, sides: int) -> int:
        return sum(self.randrange(1, sides + 1) for _ in range(count))

    def pick(self, seq: Sequence[T]) -> T:
        if not seq:
            raise ValueError("pick() from an empty sequence")
        return seq[self.below(len(seq))]

    def weighted(self, items: Sequence[tuple[T, int]]) -> T:
        if any(w < 0 for _, w in items):
            raise ValueError("negative weight")
        total = sum(w for _, w in items)
        if total <= 0:
            raise ValueError("weights sum to zero")
        roll = self.below(total)
        for item, w in items:
            if roll < w:
                return item
            roll -= w
        raise AssertionError("unreachable")

    def shuffle(self, items: list[T]) -> None:
        """Fisher-Yates, descending, in place."""
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]
