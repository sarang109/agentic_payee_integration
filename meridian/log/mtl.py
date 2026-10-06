"""Merchant Transparency Log (V2): append-only log of receiving-authority
edges and payout configurations, with brand monitors, objection records,
gossip of signed tree heads, and Algorithm 3 acceptance with probation.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from ..core.canon import canonical
from ..core.edges import ID, Edge
from ..core.ids import L0, L1, L4, layer
from ..core.keys import KeyPair, PublicKey
from .merkle import MerkleTree, leaf_hash, verify_consistency, verify_inclusion

HIGH, LOW = "high", "low"


@dataclass(frozen=True)
class STH:
    log_id: str
    size: int
    root: bytes
    timestamp: int
    view: str  # bookkeeping only; not part of the signed body
    sig: bytes = b""

    def body(self) -> dict:
        return {"log": self.log_id, "size": self.size, "root": self.root.hex(), "ts": self.timestamp}

    def verify(self, pk: PublicKey) -> bool:
        return pk.verify(self.sig, canonical(self.body()))


@dataclass
class LogEntry:
    index: int
    kind: str  # "edge" | "payout_config" | "objection"
    t_log: int
    body: dict
    leaf: bytes
    ref: Optional[str] = None  # entry key this objects to / the edge id


def edge_entry_body(e: Edge) -> dict:
    return {"edge": e.payload(), "sig_u": e.sig_u.hex(), "sig_v": e.sig_v.hex()}


def edge_risk(e: Edge) -> str:
    """High-risk: a new brand-to-entity claim or a binding to a settlement
    account; everything else is low-risk."""
    if e.etype == ID and (layer(e.src), layer(e.dst)) in ((L0, L1),):
        return HIGH
    if layer(e.dst) == L4:
        return HIGH
    return LOW


class MerchantTransparencyLog:
    def __init__(self, log_id: str = "mtl-1", key: Optional[KeyPair] = None) -> None:
        self.log_id = log_id
        self.key = key or KeyPair.from_seed(f"log:{log_id}".encode())
        self.views: Dict[str, MerkleTree] = {"main": MerkleTree()}
        self.entries: Dict[str, List[LogEntry]] = {"main": []}
        self.index_by_key: Dict[str, Dict[str, int]] = {"main": {}}
        self.objections: Dict[str, Dict[str, LogEntry]] = {"main": {}}
        self.sth_history: Dict[str, List[STH]] = {"main": []}
        self.watchers: List[Callable[[LogEntry, str], None]] = []

    @property
    def pk(self) -> PublicKey:
        return self.key.public

    # writing ---------------------------------------------------------
    def _append(self, view: str, kind: str, body: dict, t: int, key: str, ref: Optional[str] = None) -> LogEntry:
        data = canonical({"kind": kind, "t": t, "body": body})
        tree = self.views[view]
        idx = tree.append(data)
        entry = LogEntry(idx, kind, t, body, tree.leaves[idx], ref)
        self.entries[view].append(entry)
        self.index_by_key[view][key] = idx
        if kind == "objection" and ref is not None:
            self.objections[view][ref] = entry
        for w in self.watchers:
            w(entry, view)
        return entry

    def log_edge(self, e: Edge, t: int, views: Optional[List[str]] = None) -> None:
        for v in views or list(self.views):
            if e.eid not in self.index_by_key[v]:
                self._append(v, "edge", edge_entry_body(e), t, e.eid, e.eid)

    def log_payout_config(self, custodian: str, acct: str, signer_kid: str, t: int,
                          views: Optional[List[str]] = None) -> str:
        key = f"payout:{custodian}->{acct}"
        for v in views or list(self.views):
            if key not in self.index_by_key[v]:
                self._append(v, "payout_config", {"h": custodian, "acct": acct, "signer": signer_kid}, t, key, key)
        return key

    def object(self, target_key: str, by_kid: str, reason: str, t: int, view: str = "main") -> None:
        if target_key in self.objections[view]:
            return
        self._append(view, "objection", {"target": target_key, "by": by_kid, "reason": reason}, t,
                     f"obj:{target_key}", target_key)

    def equivocate(self, new_view: str, base_view: str = "main") -> None:
        """Fork a split view (A10): later appends can target one view only."""
        self.views[new_view] = self.views[base_view].copy()
        self.entries[new_view] = list(self.entries[base_view])
        self.index_by_key[new_view] = dict(self.index_by_key[base_view])
        self.objections[new_view] = dict(self.objections[base_view])
        self.sth_history[new_view] = list(self.sth_history[base_view])

    # reading ---------------------------------------------------------
    def sth(self, t: int, view: str = "main") -> STH:
        tree = self.views[view]
        s = STH(self.log_id, len(tree), tree.root(), t, view)
        s = STH(s.log_id, s.size, s.root, s.timestamp, view, self.key.sign(canonical(s.body())))
        self.sth_history[view].append(s)
        return s

    def lookup(self, key: str, view: str = "main") -> Optional[LogEntry]:
        idx = self.index_by_key[view].get(key)
        return None if idx is None else self.entries[view][idx]

    def inclusion(self, key: str, sth: STH) -> Optional[Tuple[LogEntry, List[bytes]]]:
        entry = self.lookup(key, sth.view)
        if entry is None or entry.index >= sth.size:
            return None
        return entry, self.views[sth.view].inclusion_proof(entry.index, sth.size)

    def consistency(self, old: STH, new: STH) -> Optional[List[bytes]]:
        """Proof that ``old`` is a prefix of ``new``. A log that forked cannot
        produce one across views; we return the honest proof from ``new``'s
        view and let the verifier discover that it does not check."""
        if old.size > new.size:
            return None
        if old.size == 0:
            return []
        return self.views[new.view].consistency_proof(old.size, new.size)

    def objection_for(self, key: str, sth: STH) -> Optional[LogEntry]:
        o = self.objections[sth.view].get(key)
        if o is not None and o.index < sth.size:
            return o
        return None


@dataclass
class BrandMonitor:
    """Watches the log for claims on its brand/domains and for payout
    configuration changes on its processing accounts, and objects after a
    reaction delay. ``online=False`` models a missing monitor."""

    entity_lei: str
    rep_kid: str
    domains: Set[str]
    own_accounts: Set[str]
    own_processing: Set[str]
    reaction: Callable[[random.Random], int]
    rng: random.Random
    online: bool = True
    ignore_refs: Set[str] = field(default_factory=set)  # entries this monitor misses (premise violations)
    seen_sth: List[STH] = field(default_factory=list)
    pending: List[Tuple[int, str, str]] = field(default_factory=list)

    def observe(self, entry: LogEntry, view: str) -> None:
        if not self.online or view != "main" or entry.ref in self.ignore_refs:
            return
        reason = None
        if entry.kind == "edge":
            p = entry.body["edge"]
            if p["type"] == ID and p["u"].startswith("brand:") and p["u"][6:] in self.domains \
                    and p["v"] != f"lei:{self.entity_lei}":
                reason = "foreign-entity-claims-brand"
            if p["u"] in self.own_processing and p["v"].startswith("acct:") and p["v"] not in self.own_accounts:
                reason = "unknown-payout-account"
        elif entry.kind == "payout_config":
            if entry.body["h"] in self.own_processing and entry.body["acct"] not in self.own_accounts:
                reason = "unknown-payout-account"
        if reason:
            self.pending.append((entry.t_log + self.reaction(self.rng), entry.ref or "", reason))

    def flush(self, log: MerchantTransparencyLog, now: int) -> int:
        n = 0
        keep = []
        for (t_obj, key, reason) in self.pending:
            if t_obj <= now:
                log.object(key, self.rep_kid, reason, t_obj)
                n += 1
            else:
                keep.append((t_obj, key, reason))
        self.pending = keep
        return n


class GossipPool:
    """STHs exchanged among verifiers and monitors."""

    def __init__(self) -> None:
        self.sths: List[STH] = []

    def publish(self, s: STH) -> None:
        self.sths.append(s)

    def latest_before(self, t: int) -> Optional[STH]:
        cands = [s for s in self.sths if s.timestamp <= t]
        return max(cands, key=lambda s: (s.size, s.timestamp)) if cands else None


@dataclass
class AcceptResult:
    ok: bool
    reason: str = ""
    in_probation: bool = False
    proof_bytes: int = 0


class LogVerifier:
    """Payer-side view of the MTL. Implements Algorithm 3:

    Accept(e, t) iff Incl(e, STH) and Cons(STH_prev, STH) and not Obj(e)
                     and (risk(e) = low or t - t_log(e) >= Delta)
    """

    def __init__(self, log: MerchantTransparencyLog, delta: int, gossip: Optional[GossipPool] = None,
                 view: str = "main", require_gossip_for_high: bool = True) -> None:
        self.log = log
        self.delta = delta
        self.gossip = gossip
        self.view = view
        self.prev: Optional[STH] = None
        self.equivocation = False
        self.require_gossip_for_high = require_gossip_for_high
        self._sth_cache: Tuple[int, Optional[STH]] = (-1, None)

    def refresh(self, t: int) -> Optional[STH]:
        if self._sth_cache[0] == t:
            return self._sth_cache[1]
        new = self.log.sth(t, self.view)
        if not new.verify(self.log.pk):
            self.equivocation = True
            return None
        if self.prev is not None:
            proof = self.log.consistency(self.prev, new)
            if proof is None or not verify_consistency(self.prev.size, new.size, self.prev.root, new.root, proof):
                self.equivocation = True
                return None
        self.prev = new
        self._sth_cache = (t, new)
        return new

    def gossip_check(self, mine: STH, t: int) -> bool:
        if self.gossip is None:
            return True
        peer = self.gossip.latest_before(t)
        if peer is None:
            return not self.require_gossip_for_high
        if not peer.verify(self.log.pk):
            return False
        a, b = (peer, mine) if peer.size <= mine.size else (mine, peer)
        proof = self.log.consistency(a, b)
        ok = proof is not None and verify_consistency(a.size, b.size, a.root, b.root, proof)
        if not ok:
            self.equivocation = True
        return ok

    def accept_key(self, key: str, risk: str, t: int) -> AcceptResult:
        sth = self.refresh(t)
        if sth is None or self.equivocation:
            return AcceptResult(False, "equivocation")
        inc = self.log.inclusion(key, sth)
        if inc is None:
            return AcceptResult(False, "not-logged")
        entry, proof = inc
        if not verify_inclusion(entry.leaf, entry.index, sth.size, proof, sth.root):
            return AcceptResult(False, "inclusion")
        pb = 32 * len(proof)
        if self.log.objection_for(key, sth) is not None:
            return AcceptResult(False, "objection", proof_bytes=pb)
        if risk == HIGH:
            if not self.gossip_check(sth, t):
                return AcceptResult(False, "equivocation", proof_bytes=pb)
            if t - entry.t_log < self.delta:
                return AcceptResult(False, "probation", in_probation=True, proof_bytes=pb)
        return AcceptResult(True, proof_bytes=pb)

    def accept_edge(self, e: Edge, t: int) -> AcceptResult:
        return self.accept_key(e.eid, edge_risk(e), t)


def lognormal_seconds(median_s: float, sigma: float) -> Callable[[random.Random], int]:
    mu = math.log(median_s)
    return lambda rng: int(rng.lognormvariate(mu, sigma))


__all__ = ["MerchantTransparencyLog", "BrandMonitor", "GossipPool", "LogVerifier", "STH", "edge_risk",
           "HIGH", "LOW", "lognormal_seconds", "leaf_hash"]
