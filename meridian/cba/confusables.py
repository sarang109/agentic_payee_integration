"""Unicode confusable skeletons (UTS #39, section 4).

skeleton(X) = NFD(map(NFD(X))) where map replaces each code point by its
prototype from confusables.txt.
"""

from __future__ import annotations

import os
import unicodedata
from functools import lru_cache
from typing import Dict

_DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "unicode", "confusables.txt")

# A tiny fallback table used only if the Unicode data file is missing.
_FALLBACK = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i", "ј": "j", "ѕ": "s",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "l", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "0": "O", "1": "l", "ⅼ": "l", "ı": "i", "ɡ": "g",
}


@lru_cache(maxsize=1)
def table() -> Dict[str, str]:
    path = os.path.abspath(_DATA)
    if not os.path.exists(path):
        return dict(_FALLBACK)
    out: Dict[str, str] = {}
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(";")]
            if len(parts) < 2:
                continue
            src = "".join(chr(int(c, 16)) for c in parts[0].split())
            dst = "".join(chr(int(c, 16)) for c in parts[1].split())
            out[src] = dst
    return out


@lru_cache(maxsize=65536)
def skeleton(text: str) -> str:
    t = table()
    nfd = unicodedata.normalize("NFD", text)
    mapped = "".join(t.get(ch, ch) for ch in nfd)
    return unicodedata.normalize("NFD", mapped)


def fold(text: str) -> str:
    """Skeleton, then drop separators and lowercase; used for brand names."""
    s = skeleton(text)
    return "".join(ch for ch in s.lower() if ch.isalnum())
