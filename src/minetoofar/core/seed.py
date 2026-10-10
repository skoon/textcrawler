"""Seed canonicalization and share codes (GDD 10.2)."""

import hashlib
import re
from dataclasses import dataclass

from minetoofar.core.rng import Rng

# Bump whenever generator output changes; share codes from other versions are refused.
GEN_VERSION = 1

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_VALID = re.compile(r"[A-Z0-9]{1,32}")


class SeedError(ValueError):
    pass


@dataclass(frozen=True)
class Seed:
    canonical: str

    @classmethod
    def parse(cls, text: str) -> "Seed":
        """Accept `SEED` or `<gen_version>:SEED`; spaces and hyphens in the seed are ignored."""
        body = text
        if ":" in text:
            prefix, _, body = text.partition(":")
            if not prefix.isascii() or not prefix.isdigit():
                raise SeedError(f"bad share code {text!r}: version must be a number")
            if int(prefix) != GEN_VERSION:
                raise SeedError(
                    f"share code is for generator version {prefix}; this build is {GEN_VERSION}"
                )
        canonical = re.sub(r"[\s-]", "", body).upper()
        if not _VALID.fullmatch(canonical):
            raise SeedError(f"seed must be 1-32 letters or digits (A-Z, 0-9), got {text!r}")
        return cls(canonical)

    @property
    def master64(self) -> int:
        digest = hashlib.sha256(b"AMTF|" + self.canonical.encode("ascii")).digest()
        return int.from_bytes(digest[:8], "big")

    @property
    def share_code(self) -> str:
        return f"{GEN_VERSION}:{self.canonical}"

    @property
    def display(self) -> str:
        c = self.canonical
        return "-".join(c[i : i + 4] for i in range(0, len(c), 4))

    def rng(self) -> Rng:
        return Rng(self.master64)


def seed_text_from_entropy(entropy: bytes) -> str:
    """12 Crockford base32 characters from the low 60 bits of 8 random bytes."""
    if len(entropy) != 8:
        raise ValueError("need exactly 8 bytes of entropy")
    n = int.from_bytes(entropy, "big") & ((1 << 60) - 1)
    return "".join(_CROCKFORD[(n >> shift) & 31] for shift in range(55, -1, -5))
