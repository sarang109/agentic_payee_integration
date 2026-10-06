"""Confusability features: string (k_str), visual (k_vis), semantic (k_sem)."""

from __future__ import annotations

import hashlib
import os
import re
from functools import lru_cache
from typing import Dict, List, Optional, Sequence

import numpy as np

from .confusables import fold


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1.0 - levenshtein(a, b) / max(len(a), len(b))


def domain_label(domain: str) -> str:
    d = domain.lower()
    d = re.sub(r"^www\.", "", d)
    parts = d.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "ac", "gov") and len(parts[-1]) == 2:
        return parts[-3]
    return parts[0] if len(parts) == 1 else parts[-2]


def k_str(name_x: str, dom_x: str, name_y: str, dom_y: str) -> float:
    """Edit similarity between confusable skeletons of names and of domain labels."""
    a = similarity(fold(name_x), fold(name_y))
    b = similarity(fold(domain_label(dom_x)), fold(domain_label(dom_y)))
    return max(a, b)


# ---------------------------------------------------------------- visual

def phash(img) -> int:
    """64-bit DCT perceptual hash of a PIL image."""
    from scipy.fft import dctn

    g = np.asarray(img.convert("L").resize((32, 32)), dtype=np.float64)
    d = dctn(g, norm="ortho")[:8, :8].flatten()
    med = np.median(d[1:])
    bits = 0
    for v in d:
        bits = (bits << 1) | int(v > med)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def k_vis(hash_x: Optional[int], hash_y: Optional[int]) -> float:
    if hash_x is None or hash_y is None:
        return 0.0
    return max(0.0, 1.0 - hamming(hash_x, hash_y) / 32.0)


_FONT_CACHE: Dict[int, object] = {}


def _font(size: int):
    from PIL import ImageFont

    if size not in _FONT_CACHE:
        try:
            _FONT_CACHE[size] = ImageFont.load_default(size=size)
        except TypeError:  # Pillow < 10.1
            _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]


def render_logo(text: str, color: Sequence[int], seed: int = 0, jitter: float = 0.0, size: int = 128):
    """Synthetic wordmark: brand text on a coloured tile. ``jitter`` shifts and
    recolours slightly, the way a cloned logo is re-encoded."""
    from PIL import Image, ImageDraw

    rng = np.random.default_rng(seed)
    col = tuple(int(np.clip(c + rng.normal(0, 40 * jitter), 0, 255)) for c in color)
    img = Image.new("RGB", (size, size), col)
    d = ImageDraw.Draw(img)
    label = text[:8]
    f = _font(max(14, int(size / max(3, len(label)) * 1.4)))
    dx, dy = (rng.normal(0, 4 * jitter, 2) if jitter else (0, 0))
    d.text((size / 2 + dx, size / 2 + dy), label, fill=(255, 255, 255), font=f, anchor="mm")
    return img


# ---------------------------------------------------------------- semantic

class Embedder:
    """Sentence embeddings with an open model when available; otherwise a
    hashed character n-gram embedding (recorded in results as the backend)."""

    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2", allow_model: bool = True) -> None:
        self.backend = "hashed-ngram"
        self._model = None
        if allow_model and os.environ.get("MERIDIAN_NO_EMBED_MODEL") != "1":
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(model)
                self.backend = model
            except Exception:
                self._model = None
        self._cache: Dict[str, np.ndarray] = {}

    def _hashed(self, text: str, dim: int = 512) -> np.ndarray:
        v = np.zeros(dim)
        t = f"  {text.lower()}  "
        for n in (2, 3, 4):
            for i in range(len(t) - n + 1):
                h = int.from_bytes(hashlib.blake2b(t[i:i + n].encode(), digest_size=8).digest(), "big")
                v[h % dim] += 1.0 if (h >> 63) & 1 else -1.0
        nrm = np.linalg.norm(v)
        return v / nrm if nrm else v

    def encode(self, texts: List[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            if self._model is not None:
                vecs = self._model.encode(missing, batch_size=128, normalize_embeddings=True, show_progress_bar=False)
            else:
                vecs = [self._hashed(t) for t in missing]
            for t, v in zip(missing, vecs):
                self._cache[t] = np.asarray(v, dtype=np.float32)
        return np.stack([self._cache[t] for t in texts])

    def cosine(self, a: str, b: str) -> float:
        va, vb = self.encode([a, b])
        return float(np.dot(va, vb))


def k_sem(emb: Embedder, desc_x: str, desc_y: str) -> float:
    return max(0.0, min(1.0, emb.cosine(desc_x, desc_y)))


def noisy_or(ks: Dict[str, float], w: Dict[str, float]) -> float:
    p = 1.0
    for j, k in ks.items():
        p *= 1.0 - w.get(j, 0.0) * k
    return 1.0 - p


__all__ = ["levenshtein", "similarity", "domain_label", "k_str", "phash", "hamming", "k_vis", "render_logo",
           "Embedder", "k_sem", "noisy_or"]
