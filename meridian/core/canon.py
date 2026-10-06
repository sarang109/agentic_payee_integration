"""Canonical encoding and hashing helpers.

All signed objects are serialised with sorted keys and no insignificant
whitespace (close to RFC 8785 for the value types we use: strings, ints,
bools, lists and nested dicts; floats are never signed).
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64u(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def short_hash(text: str, n: int = 24) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]
