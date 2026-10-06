"""Baselines B1-B7 and MERIDIAN configurations M1-M3 as pre-authorization
decision functions plus (for M3) the closed loop after authorization.

B1  platform curation only
B2  mandate payee binding (AP2 / Verifiable Intent): detects changes after signing
B3  merchant identity attestation (AGTP style): manifest for the displayed domain
B4  DID-to-wallet binding (PCAT P2 style): crypto rails only
B5  payee check by name (VoP style): account-to-account only
B6  agent judgment plus allow / block lists
B7  strongest combined: B2 + B3 + B4 + B5 with LEI + scoped delegation from the
    asserted entity to the payee identifier + receipts, with name anchoring
M1-G1  V1 as originally specified: PAV to the first-hop payee, agent-proposed brand
M1     V1 under the v2 core: committed route, terminal continuity (G2)
M2     M1 + V2 (confusability-bounded anchoring, transparency log with probation)
M3     M2 + V3 (closed-loop receipts, reversibility-window scheduler; synchronous
       status checks on irreversible rails)
"""

from __future__ import annotations

import hashlib
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from meridian.cba import CBA
from meridian.core.decision import ALLOW, DENY, STEP_UP
from meridian.core.keys import SIG_CHECKS
from meridian.core.pav import check_edges, pav
from meridian.core.policy import Policy
from meridian.core.routes import PAYOUT, verify_route
from meridian.log import HIGH, LogVerifier
from meridian.rws import STEP, ExecutionTrace, Hop, SchedulerParams, closed_loop, schedule
from meridian.core.discharge import TransferRecord

from .cases import Case
from .world import World

IRREVERSIBLE = {"a2a_instant", "stablecoin"}
BASELINES = ["B1", "B2", "B3", "B4", "B5", "B6", "B7"]
MERIDIAN = ["M1-G1", "M1", "M2", "M3"]
ALL_CONFIGS = BASELINES + MERIDIAN


def _norm(s: str) -> str:
    t = unicodedata.normalize("NFKC", s).casefold()
    return "".join(ch for ch in t if ch.isalnum())


def _coin(case: Case, salt: str) -> float:
    h = hashlib.sha256(f"{case.case_id}|{salt}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


@dataclass
class Ctx:
    world: World
    cba: CBA
    policy: Policy
    log_verifier: LogVerifier
    profiles: Dict
    sched: SchedulerParams = field(default_factory=SchedulerParams)
    victims: Dict[str, LogVerifier] = field(default_factory=dict)
    probation_cap: int = 0
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(0))
    use_gossip: bool = True


@dataclass
class Outcome:
    verdict: str
    stage: str
    reasons: List[str]
    level: int = -1
    mode: str = ""
    undone: bool = False
    detected: bool = False
    breach: bool = False
    detect_reason: str = ""
    decision_ms: float = 0.0
    sig_checks: int = 0


# ------------------------------------------------------------------ baselines

def b1(case: Case, ctx: Ctx) -> Outcome:
    return Outcome(ALLOW, "curation", []) if case.listing.curated else Outcome(DENY, "curation", ["not-curated"])


def b2(case: Case, ctx: Ctx) -> Outcome:
    if case.swap_after_mandate:
        return Outcome(DENY, "mandate", ["payee-changed-after-signing"])
    return Outcome(ALLOW, "mandate", [])


def b3(case: Case, ctx: Ctx) -> Outcome:
    if not case.listing.manifest_valid:
        return Outcome(STEP_UP, "identity-assertion", ["no-valid-manifest"])
    return Outcome(ALLOW, "identity-assertion", [])


def b4(case: Case, ctx: Ctx) -> Outcome:
    if case.rail != "stablecoin":
        return Outcome(ALLOW, "did-wallet", ["not-applicable"])
    if case.payment.payee in case.listing.did_wallets:
        return Outcome(ALLOW, "did-wallet", [])
    return Outcome(DENY, "did-wallet", ["wallet-not-bound"])


def _vop(ctx: Ctx, acct: str, name: Optional[str] = None, lei: Optional[str] = None) -> str:
    bank_name = acct.split(":", 1)[1].split("/", 1)[0] if acct.startswith("acct:") else ""
    bank = ctx.world.banks.get(bank_name)
    if bank is None:
        return "NOT_POSSIBLE"
    return bank.vop(acct, name=name, lei=lei)


def b5(case: Case, ctx: Ctx) -> Outcome:
    if case.rail != "a2a_instant":
        return Outcome(ALLOW, "vop", ["not-applicable"])
    r = _vop(ctx, case.payment.payee, name=case.vop_name)
    if r == "MATCH":
        return Outcome(ALLOW, "vop", [])
    if r == "CLOSE_MATCH":
        return Outcome(STEP_UP, "vop", ["close-match"])
    return Outcome(DENY, "vop", [r.lower()])


def b6(case: Case, ctx: Ctx) -> Outcome:
    if case.listing.known_bad:
        return Outcome(DENY, "lists", ["blocklisted"])
    if case.listing.looks_off and _coin(case, "agent-judgment") < 0.3:
        return Outcome(STEP_UP, "agent-judgment", ["agent-suspicious"])
    return Outcome(ALLOW, "lists", [])


def b7(case: Case, ctx: Ctx) -> Outcome:
    lst = case.listing
    if not lst.manifest_valid:
        return Outcome(STEP_UP, "identity-assertion", ["no-valid-manifest"])
    words = _norm(case.user_words)
    if not (words and (words in _norm(lst.legal_name) or words == _norm(lst.display_name)
                       or words in _norm(lst.display_name))):
        return Outcome(STEP_UP, "name-anchor", ["name-mismatch"])
    if case.swap_after_mandate:
        return Outcome(DENY, "mandate", ["payee-changed-after-signing"])
    if case.rail == "stablecoin" and case.payment.payee not in lst.did_wallets:
        return Outcome(DENY, "did-wallet", ["wallet-not-bound"])
    if case.rail == "a2a_instant":
        r = _vop(ctx, case.payment.payee, lei=lst.lei)
        if r != "MATCH":
            return Outcome(DENY, "vop-lei", [r.lower()])
    # scoped receiving delegation from the asserted entity to the payee id
    b = case.bundle
    if b is None or not b.rap.edges:
        return Outcome(STEP_UP, "delegation", ["no-delegation"])
    edges = b.rap.edges
    start = next((i for i, e in enumerate(edges) if e.src == f"lei:{lst.lei}"), None)
    if start is None or edges[-1].dst != case.payment.payee:
        return Outcome(STEP_UP, "delegation", ["no-delegation-from-asserted-entity"])
    pol = Policy(rho=ctx.policy.rho, grammar=False)
    pc = check_edges(edges[start:], b.rap.status, case.payment.tuple, case.payment.t, pol, ctx.world.trust)
    if not pc.ok:
        return Outcome(DENY if pc.tamper else STEP_UP, "delegation", pc.reasons)
    return Outcome(ALLOW, "b7", [])


BASELINE_FNS = {"B1": b1, "B2": b2, "B3": b3, "B4": b4, "B5": b5, "B6": b6, "B7": b7}


# ------------------------------------------------------------------ MERIDIAN

def _policy_for(case: Case, ctx: Ctx, synchronous_irreversible: bool) -> Policy:
    p = ctx.policy
    if synchronous_irreversible and case.rail in IRREVERSIBLE:
        return Policy(**{**p.__dict__, "rho": 0})
    return p


def m1_g1(case: Case, ctx: Ctx) -> Outcome:
    pol = Policy(**{**ctx.policy.__dict__, "grammar": False})
    d = pav(case.bundle.rap if case.bundle else None, case.payment, case.listing.brand_claim, pol, ctx.world.trust)
    return Outcome(d.verdict, d.stage, d.reasons, d.level, sig_checks=d.sig_checks)


def m1(case: Case, ctx: Ctx) -> Outcome:
    d = verify_route(case.bundle, case.payment, case.listing.brand_claim, ctx.policy, ctx.world.trust)
    return Outcome(d.verdict, d.stage, d.reasons, d.level, sig_checks=d.sig_checks)


def anchor(case: Case, ctx: Ctx):
    extra = [case.listing.candidate] if case.listing.candidate is not None else []
    return ctx.cba.anchor(case.user_words, extra, now=case.payment.t)


def log_checks(case: Case, ctx: Ctx, verifier: LogVerifier) -> Optional[Outcome]:
    b = case.bundle
    edges = list(b.rap.edges) + list(b.onward) + ([b.terminal] if b.terminal is not None else [])
    probation = []
    for e in edges:
        r = verifier.accept_edge(e, case.payment.t)
        if not r.ok:
            if r.reason == "probation":
                probation.append(e.eid)
                continue
            return Outcome(DENY if r.reason == "objection" else STEP_UP, "mtl", [f"mtl-{r.reason}"])
    for c in b.commitments:
        if c.kind == PAYOUT:
            r = verifier.accept_key(f"payout:{c.custodian}->{c.next_hop}", HIGH, case.payment.t)
            if not r.ok:
                if r.reason == "probation":
                    probation.append(c.custodian)
                    continue
                return Outcome(DENY if r.reason == "objection" else STEP_UP, "mtl", [f"mtl-payout-{r.reason}"])
    if probation and case.payment.amount > ctx.probation_cap:
        return Outcome(STEP_UP, "mtl", ["mtl-probation"])
    return None


def m2(case: Case, ctx: Ctx, synchronous_irreversible: bool = False) -> Outcome:
    a = anchor(case, ctx)
    if not a.committed:
        return Outcome(STEP_UP, "cba", ["cba-" + ("-".join(a.question) or "ambiguous")])
    pol = _policy_for(case, ctx, synchronous_irreversible)
    d = verify_route(case.bundle, case.payment, a.brand, pol, ctx.world.trust)
    out = Outcome(d.verdict, d.stage, d.reasons, d.level, sig_checks=d.sig_checks)
    if d.verdict != ALLOW:
        return out
    verifier = ctx.victims.get(case.log_view, ctx.log_verifier) if case.log_view else ctx.log_verifier
    bad = log_checks(case, ctx, verifier)
    if bad is not None:
        bad.level = d.level
        return bad
    return out


def execution_trace(case: Case, ctx: Ctx, mode: str) -> ExecutionTrace:
    prof = ctx.profiles[case.rail]
    rng = ctx.rng
    window_end = float(prof.window(rng, 1)[0])
    base = window_end if prof.onward_after_window else 0.0
    hops = []
    t = base
    for (src, dst, key) in case.exec_hops:
        t += float(prof.transfer_delay(rng, 1)[0]) + 1.0
        rec = TransferRecord.issue(key, case.payment.payment_id, src, dst, case.payment.amount, int(t)) if key else None
        hops.append(Hop(src, dst, case.payment.amount, t, rec))
    credit_t = (hops[-1].t if hops else 0.0) + 2.0
    return ExecutionTrace(case.exec_first_hop, hops, case.exec_terminal, window_end, credit_t,
                          case.late_evidence_after)


def m3(case: Case, ctx: Ctx) -> Outcome:
    out = m2(case, ctx, synchronous_irreversible=True)
    if out.verdict != ALLOW:
        return out
    prof = ctx.profiles[case.rail]
    sch = schedule(prof, case.payment.amount / 100.0, out.level, ctx.sched)
    out.mode = sch.mode
    if sch.mode == STEP:
        out.verdict, out.stage, out.reasons = STEP_UP, "rws", ["rws-step-up"]
        return out
    trace = execution_trace(case, ctx, sch.mode)
    v3 = closed_loop(case.bundle, case.payment.payee, trace, prof, sch.mode, case.corrupt_observers, ctx.rng,
                     ctx.world.trust)
    out.undone = v3.undone
    out.detected = v3.detected
    out.breach = v3.breach is not None
    out.detect_reason = v3.reason
    return out


MERIDIAN_FNS = {"M1-G1": m1_g1, "M1": m1, "M2": m2, "M3": m3}


def evaluate(case: Case, ctx: Ctx, config: str) -> Outcome:
    fn = BASELINE_FNS.get(config) or MERIDIAN_FNS[config]
    t0 = time.perf_counter()
    s0 = SIG_CHECKS.value
    out = fn(case, ctx)
    out.decision_ms = (time.perf_counter() - t0) * 1000
    if not out.sig_checks:
        out.sig_checks = SIG_CHECKS.value - s0
    if config == "B7" and out.verdict == ALLOW and case.exec_first_hop != case.payment.payee \
            and case.receipt_visible and case.rail not in IRREVERSIBLE:
        out.undone, out.detected, out.detect_reason = True, True, "receipt-first-hop"
    return out


__all__ = ["Ctx", "Outcome", "evaluate", "ALL_CONFIGS", "BASELINES", "MERIDIAN", "anchor", "IRREVERSIBLE",
           "execution_trace"]
