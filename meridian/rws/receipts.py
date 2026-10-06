"""V3: closed-loop destination receipts.

After authorization independent observers report what happened; each report
reaches a stated level (F1). The verifier compares observations with the
committed route and voids before capture, refunds from escrow or recalls when
it can, and otherwise files a breach certificate (Theorem 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set, Tuple

import numpy as np

from ..core.decision import G1, G3, G4, G_NONE
from ..core.discharge import BreachCertificate, TransferRecord, find_breach
from ..core.policy import TrustStore
from ..core.routes import RouteBundle
from .rails import RailProfile
from .scheduler import ESCROW, POST, PRE, STEP


@dataclass
class Hop:
    src: str
    dst: str
    amount: int
    t: float
    record: Optional[TransferRecord] = None


@dataclass
class ExecutionTrace:
    """What the rail actually did, in seconds after authorization."""

    auth_payee: str
    hops: List[Hop]
    terminal: str
    window_end: float
    credit_t: float
    late_evidence_t: Optional[float] = None  # revocation / objection becomes visible


@dataclass
class V3Outcome:
    mode: str
    deviation: bool
    detected: bool
    detect_t: Optional[float]
    undone: bool
    confirmed_level: int
    breach: Optional[BreachCertificate] = None
    reason: str = ""


def _earliest_honest(latencies: Sequence[float], corrupt: int) -> float:
    """The adversary corrupts the fastest ``corrupt`` observers."""
    xs = sorted(latencies)
    return xs[corrupt] if corrupt < len(xs) else float("inf")


def closed_loop(bundle: Optional[RouteBundle], expected_payee: str, trace: ExecutionTrace, profile: RailProfile,
                mode: str, corrupt: int, rng: np.random.Generator, trust: TrustStore) -> V3Outcome:
    committed = {c.custodian: c for c in (bundle.commitments if bundle else [])}
    committed_terminal = bundle.committed_terminal() if bundle else None

    detections: List[Tuple[float, str]] = []

    def sample(spec) -> float:
        return float(spec.latency(rng, 1)[0])

    # G1: first-hop identity from issuer / wallet / PSP records
    if trace.auth_payee != expected_payee:
        lats = [sample(o) for o in profile.observers_at(G1)]
        detections.append((_earliest_honest(lats, corrupt), "first-hop"))
    # G3: onward transfers against commitments
    for hop in trace.hops:
        c = committed.get(hop.src)
        if c is not None and (hop.dst != c.next_hop or hop.amount < c.amount):
            lats = [sample(o) for o in profile.observers_at(G3)]
            detections.append((hop.t + _earliest_honest(lats, corrupt), "transfer"))
    # G4: arrival
    if committed_terminal is not None and trace.terminal != committed_terminal:
        lats = [sample(o) for o in profile.observers_at(G4)]
        detections.append((trace.credit_t + _earliest_honest(lats, corrupt), "arrival"))
    if trace.late_evidence_t is not None:
        detections.append((trace.late_evidence_t, "late-evidence"))

    deviation = bool(detections)
    detect_t = min((t for t, _ in detections), default=None)
    reason = min(detections)[1] if detections else ""

    level = G_NONE
    if trace.auth_payee == expected_payee and profile.observers_at(G1):
        level = G1
    if bundle and all(not (h.src in committed and h.dst != committed[h.src].next_hop) for h in trace.hops) \
            and profile.observers_at(G3):
        level = max(level, G3)
    if committed_terminal and trace.terminal == committed_terminal and profile.observers_at(G4):
        level = max(level, G4)

    undone = False
    if deviation and detect_t is not None and np.isfinite(detect_t) and mode in (POST, ESCROW):
        d = float(profile.decision(rng, 1)[0])
        if mode == POST:
            v = float(profile.void(rng, 1)[0])
            ok = detect_t + d + v <= trace.window_end and rng.random() < profile.void_success
        else:
            v = float(profile.escrow_latency(rng, 1)[0])
            ok = detect_t + d + v <= profile.escrow_window and rng.random() < 0.999
        undone = bool(ok)

    breach = None
    if deviation and bundle is not None:
        recs = [h.record for h in trace.hops if h.record is not None]
        breach = find_breach(bundle, recs, trust)
    return V3Outcome(mode, deviation, deviation and detect_t is not None and np.isfinite(detect_t), detect_t,
                     undone, level, breach, reason)
