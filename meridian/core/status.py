"""Revocation status lists (bitstring status lists, W3C style).

Each issuer publishes signed snapshots of its list. A verifier with
freshness bound rho accepts a snapshot whose timestamp is no older than rho;
in the worst case it therefore sees the list as it was at t - rho, which is
what ``StatusRegistry.view`` models.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .canon import b64u, canonical
from .edges import StatusRef
from .keys import KeyPair, PublicKey


@dataclass(frozen=True)
class StatusSnapshot:
    list_id: str
    issued_at: int
    bits: bytes
    issuer_kid: str
    sig: bytes

    def body(self) -> dict:
        return {"list": self.list_id, "iat": self.issued_at, "bits": b64u(zlib.compress(self.bits)), "iss": self.issuer_kid}

    def verify(self, pk: PublicKey) -> bool:
        return pk.verify(self.sig, canonical(self.body()))

    def revoked(self, index: int) -> bool:
        byte, bit = divmod(index, 8)
        if byte >= len(self.bits):
            return False
        return bool(self.bits[byte] >> (7 - bit) & 1)

    def wire_size(self) -> int:
        return len(canonical(self.body())) + len(self.sig)


@dataclass
class StatusList:
    list_id: str
    key: KeyPair
    capacity: int = 4096
    _next: int = 0
    _events: List[Tuple[int, int, bool]] = field(default_factory=list)  # (t, idx, revoked)
    _cache: Dict[int, StatusSnapshot] = field(default_factory=dict)

    def allocate(self) -> StatusRef:
        if self._next >= self.capacity:
            raise RuntimeError(f"status list {self.list_id} is full")
        ref = StatusRef(self.list_id, self._next)
        self._next += 1
        return ref

    def set(self, index: int, t: int, revoked: bool = True) -> None:
        self._events.append((t, index, revoked))
        self._events.sort(key=lambda e: e[0])
        self._cache.clear()

    def revoke(self, index: int, t: int) -> None:
        self.set(index, t, True)

    def state_at(self, t: int) -> bytearray:
        bits = bytearray((self.capacity + 7) // 8)
        for (te, idx, rev) in self._events:
            if te > t:
                break
            byte, bit = divmod(idx, 8)
            if rev:
                bits[byte] |= 1 << (7 - bit)
            else:
                bits[byte] &= ~(1 << (7 - bit)) & 0xFF
        return bits

    def last_change_before(self, t: int) -> int:
        times = [e[0] for e in self._events if e[0] <= t]
        return max(times) if times else 0

    def snapshot(self, t: int) -> StatusSnapshot:
        # Snapshots only change when the list changes; key the cache on the
        # last event time so repeated verifications are cheap.
        key = (t, self.last_change_before(t))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        bits = bytes(self.state_at(t))
        body = {"list": self.list_id, "iat": t, "bits": b64u(zlib.compress(bits)), "iss": self.key.kid}
        snap = StatusSnapshot(self.list_id, t, bits, self.key.kid, self.key.sign(canonical(body)))
        if len(self._cache) > 4096:
            self._cache.clear()
        self._cache[key] = snap
        return snap


class StatusRegistry:
    def __init__(self) -> None:
        self.lists: Dict[str, StatusList] = {}

    def create(self, list_id: str, key: KeyPair, capacity: int = 4096) -> StatusList:
        sl = StatusList(list_id, key, capacity)
        self.lists[list_id] = sl
        return sl

    def snapshot_for(self, ref: StatusRef, now: int, rho: int) -> Optional[StatusSnapshot]:
        sl = self.lists.get(ref.list_id)
        if sl is None:
            return None
        # Worst case cache: the verifier's freshest acceptable snapshot is
        # rho old. rho = 0 means a synchronous check at commit time.
        return sl.snapshot(max(0, now - rho))

    def revoked_now(self, ref: StatusRef, t: int) -> bool:
        sl = self.lists[ref.list_id]
        bits = sl.state_at(t)
        byte, bit = divmod(ref.index, 8)
        return bool(bits[byte] >> (7 - bit) & 1)

    def all_snapshot_times(self) -> List[int]:
        out = []
        for sl in self.lists.values():
            out.extend(e[0] for e in sl._events)
        return sorted(out)


def snapshot_age_ok(snap: StatusSnapshot, now: int, rho: int) -> bool:
    return now - snap.issued_at <= rho


__all__ = ["StatusList", "StatusRegistry", "StatusSnapshot", "snapshot_age_ok"]
