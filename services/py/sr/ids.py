"""Time-ordered IDs (ULID, DC §1): <prefix>_<26 chars Crockford base32>."""

from __future__ import annotations

import os
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid(ms: int | None = None) -> str:
    t = int(time.time() * 1000) if ms is None else ms
    rnd = int.from_bytes(os.urandom(10), "big")
    n = (t << 80) | rnd
    out = []
    for _ in range(26):
        out.append(_ALPHABET[n & 31])
        n >>= 5
    return "".join(reversed(out))


def new_id(prefix: str, ms: int | None = None) -> str:
    return f"{prefix}_{ulid(ms)}"
