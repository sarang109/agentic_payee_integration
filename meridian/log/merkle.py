"""Merkle tree, inclusion and consistency proofs (RFC 6962 / RFC 9162 s2.1)."""

from __future__ import annotations

import hashlib
from typing import Dict, List, Sequence, Tuple


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


EMPTY_ROOT = hashlib.sha256(b"").digest()


def _split(n: int) -> int:
    """Largest power of two strictly smaller than n (n >= 2)."""
    k = 1
    while k << 1 < n:
        k <<= 1
    return k


class MerkleTree:
    def __init__(self, leaves: Sequence[bytes] = ()) -> None:
        self.leaves: List[bytes] = list(leaves)  # leaf hashes
        self._cache: Dict[Tuple[int, int], bytes] = {}

    def __len__(self) -> int:
        return len(self.leaves)

    def append(self, data: bytes) -> int:
        self.leaves.append(leaf_hash(data))
        return len(self.leaves) - 1

    def append_hash(self, lh: bytes) -> int:
        self.leaves.append(lh)
        return len(self.leaves) - 1

    def copy(self, size: int | None = None) -> "MerkleTree":
        t = MerkleTree(self.leaves[: len(self.leaves) if size is None else size])
        t._cache = {k: v for k, v in self._cache.items() if k[0] + k[1] <= len(t.leaves)}
        return t

    def _mth(self, start: int, n: int) -> bytes:
        if n == 0:
            return EMPTY_ROOT
        if n == 1:
            return self.leaves[start]
        full = n & (n - 1) == 0
        if full:
            h = self._cache.get((start, n))
            if h is not None:
                return h
        k = _split(n)
        h = node_hash(self._mth(start, k), self._mth(start + k, n - k))
        if full:
            self._cache[(start, n)] = h
        return h

    def root(self, size: int | None = None) -> bytes:
        n = len(self.leaves) if size is None else size
        if n > len(self.leaves):
            raise ValueError("size beyond tree")
        return self._mth(0, n)

    def _path(self, m: int, start: int, n: int) -> List[bytes]:
        if n <= 1:
            return []
        k = _split(n)
        if m < k:
            return self._path(m, start, k) + [self._mth(start + k, n - k)]
        return self._path(m - k, start + k, n - k) + [self._mth(start, k)]

    def inclusion_proof(self, index: int, size: int | None = None) -> List[bytes]:
        n = len(self.leaves) if size is None else size
        if not 0 <= index < n:
            raise IndexError(index)
        return self._path(index, 0, n)

    def _subproof(self, m: int, start: int, n: int, b: bool) -> List[bytes]:
        if m == n:
            return [] if b else [self._mth(start, n)]
        k = _split(n)
        if m <= k:
            return self._subproof(m, start, k, b) + [self._mth(start + k, n - k)]
        return self._subproof(m - k, start + k, n - k, False) + [self._mth(start, k)]

    def consistency_proof(self, first: int, second: int | None = None) -> List[bytes]:
        n = len(self.leaves) if second is None else second
        if not 0 < first <= n:
            raise ValueError("bad sizes")
        if first == n:
            return []
        return self._subproof(first, 0, n, True)


def verify_inclusion(lh: bytes, index: int, size: int, proof: Sequence[bytes], root: bytes) -> bool:
    if index >= size:
        return False
    fn, sn, r = index, size - 1, lh
    for p in proof:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = node_hash(p, r)
            if not fn & 1:
                while not fn & 1 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root


def verify_consistency(first: int, second: int, first_root: bytes, second_root: bytes, proof: Sequence[bytes]) -> bool:
    if first > second:
        return False
    if first == second:
        return first_root == second_root and not proof
    if first == 0:
        return True
    if not proof:
        return False
    path = list(proof)
    if first & (first - 1) == 0:
        path = [first_root] + path
    fn, sn = first - 1, second - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    fr = sr = path[0]
    for c in path[1:]:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            fr = node_hash(c, fr)
            sr = node_hash(c, sr)
            if not fn & 1:
                while not fn & 1 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            sr = node_hash(sr, c)
        fn >>= 1
        sn >>= 1
    return fr == first_root and sr == second_root and sn == 0


def root_of_hashes(hashes: Sequence[bytes]) -> bytes:
    """Iterative root for very large trees (no proofs); used by E8."""
    if not hashes:
        return EMPTY_ROOT
    # RFC 6962 trees are left-balanced; build by recursive split over
    # contiguous power-of-two blocks so the result matches MerkleTree.root().
    n = len(hashes)
    stack: List[Tuple[int, bytes]] = []
    for lh in hashes:
        h, size = lh, 1
        while stack and stack[-1][0] == size:
            s, left = stack.pop()
            h = node_hash(left, h)
            size += s
        stack.append((size, h))
    h = stack[-1][1]
    for _, left in reversed(stack[:-1]):
        h = node_hash(left, h)
    assert n > 0
    return h
