"""Private log lookups for V4.

KAnonLookup  the client reveals only an L-bit prefix of H(key); the server
             returns the whole bucket (Have-I-Been-Pwned style range query).
XorPIR       two-server information-theoretic PIR: the client sends a random
             subset S to server A and S xor {i} to server B; neither server
             alone learns i (non-collusion assumption).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


def h(key: str) -> bytes:
    return hashlib.sha256(key.encode()).digest()


class KAnonLookup:
    def __init__(self, keys_to_values: Dict[str, bytes], prefix_bits: int = 16) -> None:
        self.bits = prefix_bits
        self.buckets: Dict[int, List[Tuple[bytes, bytes]]] = {}
        for k, v in keys_to_values.items():
            hk = h(k)
            self.buckets.setdefault(self._prefix(hk), []).append((hk, v))
        self.queries: List[int] = []

    def _prefix(self, hk: bytes) -> int:
        return int.from_bytes(hk[:4], "big") >> (32 - self.bits)

    def server_answer(self, prefix: int) -> List[Tuple[bytes, bytes]]:
        self.queries.append(prefix)
        return self.buckets.get(prefix, [])

    def query(self, key: str) -> Tuple[Optional[bytes], int, int]:
        """Returns (value, anonymity set size, response bytes)."""
        hk = h(key)
        bucket = self.server_answer(self._prefix(hk))
        val = next((v for (bk, v) in bucket if bk == hk), None)
        return val, len(bucket), sum(len(a) + len(b) for a, b in bucket)


@dataclass
class XorPIR:
    records: np.ndarray  # shape (N, record_bytes), uint8

    @classmethod
    def from_records(cls, recs: Sequence[bytes], record_bytes: int) -> "XorPIR":
        arr = np.zeros((len(recs), record_bytes), dtype=np.uint8)
        for i, r in enumerate(recs):
            b = r[:record_bytes]
            arr[i, : len(b)] = np.frombuffer(b, dtype=np.uint8)
        return cls(arr)

    def server(self, selection: np.ndarray) -> np.ndarray:
        sel = self.records[selection.astype(bool)]
        return np.bitwise_xor.reduce(sel, axis=0) if len(sel) else np.zeros(self.records.shape[1], dtype=np.uint8)

    def query(self, index: int, rng: np.random.Generator) -> Tuple[bytes, int]:
        n = self.records.shape[0]
        s = rng.integers(0, 2, n, dtype=np.uint8)
        s2 = s.copy()
        s2[index] ^= 1
        a = self.server(s)
        b = self.server(s2)
        upload = 2 * ((n + 7) // 8)
        return bytes(np.bitwise_xor(a, b)), upload + 2 * self.records.shape[1]
