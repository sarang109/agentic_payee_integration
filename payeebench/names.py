"""Synthetic brand names and dnstwist-style lookalike generation.

Synthetic names keep the benchmark free of real trademarks. The same
lookalike techniques are applied to real Tranco domains in E4.
"""

from __future__ import annotations

import random
from typing import List, Tuple

ONSETS = ["b", "br", "c", "cl", "d", "dr", "f", "fl", "g", "gr", "h", "j", "k", "l", "m", "n", "p", "pr", "qu",
          "r", "s", "st", "t", "tr", "v", "w", "z"]
VOWELS = ["a", "e", "i", "o", "u", "ai", "ea", "io", "ou"]
CODAS = ["", "n", "r", "l", "x", "s", "m", "nd", "rk", "st", "va", "ra", "na", "lo", "ex", "ion"]

HOMOGLYPHS = {
    "a": ["а", "ɑ"], "c": ["с", "ϲ"], "e": ["е", "ҽ"], "i": ["і", "ı", "1"], "j": ["ј"], "l": ["1", "ⅼ", "I"],
    "o": ["о", "0", "ο"], "p": ["р", "ρ"], "s": ["ѕ"], "x": ["х", "χ"], "y": ["у"], "k": ["κ"], "n": ["ո"],
    "m": ["rn"], "w": ["vv"], "d": ["ԁ"], "g": ["ɡ"], "h": ["һ"],
}
AFFIXES_PRE = ["shop", "buy", "my", "the", "get", "official"]
AFFIXES_POST = ["official", "store", "shop", "outlet", "online", "direct", "sale", "deals", "us", "uk"]
TLDS = ["com", "net", "co", "shop", "store", "online", "co.uk", "io", "app"]
SEMANTIC = {"outlet": "Outlet", "store": "Store", "official": "Official", "deals": "Deals"}

TECHNIQUES = ["homoglyph", "typo-omission", "typo-swap", "typo-repeat", "typo-replace", "affix", "tld-swap",
              "hyphenation", "name-clone", "semantic-twin"]


def brand_name(rng: random.Random) -> str:
    n = rng.choice([2, 2, 3])
    s = "".join(rng.choice(ONSETS) + rng.choice(VOWELS) for _ in range(n - 1)) + rng.choice(ONSETS) + \
        rng.choice(VOWELS) + rng.choice(CODAS)
    return s.capitalize()


def unique_brands(rng: random.Random, n: int) -> List[str]:
    seen, out = set(), []
    while len(out) < n:
        b = brand_name(rng)
        if 4 <= len(b) <= 11 and b.lower() not in seen:
            seen.add(b.lower())
            out.append(b)
    return out


def _keyboard_neighbor(c: str, rng: random.Random) -> str:
    rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
    for r in rows:
        if c in r:
            i = r.index(c)
            opts = [r[j] for j in (i - 1, i + 1) if 0 <= j < len(r)]
            return rng.choice(opts)
    return c


def lookalike(name: str, domain: str, technique: str, rng: random.Random) -> Tuple[str, str]:
    """Return (display name, domain) for a lookalike of (name, domain)."""
    label, tld = domain.split(".", 1)
    low = label.lower()
    if technique == "homoglyph":
        idx = [i for i, ch in enumerate(low) if ch in HOMOGLYPHS]
        if not idx:
            return lookalike(name, domain, "typo-replace", rng)
        i = rng.choice(idx)
        g = rng.choice(HOMOGLYPHS[low[i]])
        disp = name[:i] + (g.upper() if name[i].isupper() and len(g) == 1 else g) + name[i + 1:]
        if g.isascii():
            dom_label = low[:i] + g.lower() + low[i + 1:]
        else:
            # IDN label: encode the way registries store it
            dom_label = (low[:i] + g + low[i + 1:]).encode("idna").decode("ascii")
        return disp, f"{dom_label}.{tld}"
    if technique == "typo-omission" and len(low) > 4:
        i = rng.randrange(1, len(low) - 1)
        nl = low[:i] + low[i + 1:]
        return nl.capitalize(), f"{nl}.{tld}"
    if technique == "typo-swap" and len(low) > 3:
        i = rng.randrange(0, len(low) - 1)
        nl = low[:i] + low[i + 1] + low[i] + low[i + 2:]
        if nl == low:
            return lookalike(name, domain, "typo-repeat", rng)
        return nl.capitalize(), f"{nl}.{tld}"
    if technique == "typo-repeat":
        i = rng.randrange(0, len(low))
        nl = low[:i] + low[i] + low[i:]
        return nl.capitalize(), f"{nl}.{tld}"
    if technique == "typo-replace":
        i = rng.randrange(0, len(low))
        nl = low[:i] + _keyboard_neighbor(low[i], rng) + low[i + 1:]
        return nl.capitalize(), f"{nl}.{tld}"
    if technique == "affix":
        if rng.random() < 0.5:
            a = rng.choice(AFFIXES_POST)
            return f"{name} {a.capitalize()}", f"{low}-{a}.{tld}" if rng.random() < 0.5 else f"{low}{a}.{tld}"
        a = rng.choice(AFFIXES_PRE)
        return f"{a.capitalize()} {name}", f"{a}{low}.{tld}"
    if technique == "tld-swap":
        t = rng.choice([x for x in TLDS if x != tld])
        return name, f"{low}.{t}"
    if technique == "hyphenation" and len(low) > 3:
        i = rng.randrange(1, len(low) - 1)
        return name, f"{low[:i]}-{low[i:]}.{tld}"
    if technique == "name-clone":
        return name, f"{low}-{rng.choice(['store', 'shop', 'app', 'official'])}.{rng.choice(['net', 'shop', 'store'])}"
    if technique == "semantic-twin":
        w = rng.choice(list(SEMANTIC))
        return f"{name} {SEMANTIC[w]}", f"{low}{w}.{tld}"
    return lookalike(name, domain, "typo-replace", rng)
