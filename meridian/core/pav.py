"""Receiving-Authority Proof (RAP), payee binding token and Algorithm 1 (PAV).

Like a TLS certificate chain, the merchant or its PSP presents the path and
the verifier checks it: 2k + 1 signatures (two per edge plus the binding
token), up to 3k + 1 when each status proof is a signed list, and a scope
meet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import grammar
from .canon import canonical, digest
from .decision import ALLOW, DENY, G1, STEP_UP, Decision, Payment
from .edges import Edge
from .keys import SIG_CHECKS, KeyPair
from .policy import Policy, TrustStore, allowed
from .scope import PaymentTuple, Scope
from .status import StatusSnapshot

TAMPER_REASONS = {"sig-authorize", "sig-accept", "beta-sig", "beta-mismatch", "chain-break", "payee-mismatch", "status-sig"}


@dataclass(frozen=True)
class BindingToken:
    """beta: the L3 operator's signature over checkout digest, amount and p."""

    payment_id: str
    cart_digest: str
    amount: int
    currency: str
    payee: str
    nonce: str
    exp: int
    signer_kid: str
    sig: bytes = b""

    def body(self) -> dict:
        return {
            "pid": self.payment_id,
            "cart": self.cart_digest,
            "amt": self.amount,
            "cur": self.currency,
            "payee": self.payee,
            "nonce": self.nonce,
            "exp": self.exp,
            "signer": self.signer_kid,
        }

    @property
    def digest(self) -> str:
        return digest(self.body())

    @classmethod
    def issue(cls, key: KeyPair, payment: Payment, ttl: int = 900) -> "BindingToken":
        tok = cls(payment.payment_id, payment.cart_digest, payment.amount, payment.currency,
                  payment.payee, payment.nonce, payment.t + ttl, key.kid)
        return cls(**{**tok.__dict__, "sig": key.sign(canonical(tok.body()))})

    def wire_size(self) -> int:
        return len(canonical(self.body())) + len(self.sig)


@dataclass
class RAP:
    edges: List[Edge]
    status: Dict[str, StatusSnapshot] = field(default_factory=dict)
    binding: Optional[BindingToken] = None

    def wire_size(self) -> int:
        n = sum(e.wire_size() for e in self.edges)
        n += sum(s.wire_size() for s in self.status.values())
        if self.binding:
            n += self.binding.wire_size()
        return n


@dataclass
class PathCheck:
    ok: bool
    reasons: List[str]
    scope: Optional[Scope]
    principal: Optional[str]
    tamper: bool
    grammar_state: int = 0


def check_edges(
    edges: Sequence[Edge],
    status: Dict[str, StatusSnapshot],
    t: PaymentTuple,
    now: int,
    policy: Policy,
    trust: TrustStore,
    require_terminal: bool = False,
    start_principal: Optional[str] = None,
    snap_ok: Optional[Dict[str, bool]] = None,
) -> PathCheck:
    """Step 3-4 of PAV for an arbitrary chained edge sequence."""
    reasons: List[str] = []
    snap_ok = {} if snap_ok is None else snap_ok
    sc = Scope.top()
    for i, e in enumerate(edges):
        if i > 0 and edges[i - 1].dst != e.src:
            reasons.append("chain-break")
            break
        ok, why = allowed(e, trust, policy)
        if not ok:
            reasons.append(why)
            break
        if not e.valid_at(now):
            reasons.append("expired")
            break
        snap = status.get(e.status.list_id)
        if snap is None:
            reasons.append("status-missing")
            break
        # either party to a bilateral edge may host its status entry
        hosts = (e.issuer_kid, e.acceptor_kid)
        if snap.list_id not in snap_ok:
            pk = trust.pk(snap.issuer_kid)
            snap_ok[snap.list_id] = pk is not None and snap.verify(pk)
        if not snap_ok[snap.list_id] or snap.issuer_kid not in hosts:
            reasons.append("status-sig")
            break
        if now - snap.issued_at > policy.rho:
            reasons.append("status-stale")
            break
        if snap.revoked(e.status.index):
            reasons.append("revoked")
            break
        sc = sc.meet(e.scope)
    principal = None
    gstate = 0
    if not reasons:
        if policy.use_scope_meet and not sc.contains(t):
            reasons.append("scope")
        if policy.grammar:
            g = grammar.run(edges, require_terminal=require_terminal, start_principal=start_principal)
            principal, gstate = g.principal, g.state
            if not g.ok:
                reasons.append("grammar:" + g.reason)
        else:
            g = grammar.run(edges, require_terminal=False, start_principal=start_principal)
            principal, gstate = g.principal, g.state
    tamper = any(r in TAMPER_REASONS for r in reasons)
    return PathCheck(not reasons, reasons, sc if not reasons else None, principal, tamper, gstate)


def verify_binding(beta: Optional[BindingToken], payment: Payment, last_edge: Edge, trust: TrustStore) -> Tuple[bool, str]:
    if beta is None:
        return False, "beta-missing"
    if beta.signer_kid != last_edge.acceptor_kid:
        return False, "beta-signer"
    pk = trust.pk(beta.signer_kid)
    if pk is None or not pk.verify(beta.sig, canonical(beta.body())):
        return False, "beta-sig"
    if (
        beta.payee != payment.payee
        or beta.amount != payment.amount
        or beta.currency != payment.currency
        or beta.cart_digest != payment.cart_digest
        or beta.payment_id != payment.payment_id
        or beta.nonce != payment.nonce
    ):
        return False, "beta-mismatch"
    if payment.t > beta.exp:
        return False, "beta-expired"
    return True, ""


def pav(rap: Optional[RAP], payment: Payment, anchor: Optional[str], policy: Policy, trust: TrustStore) -> Decision:
    """Algorithm 1: Path-Authorized Verification (V1b)."""
    start = SIG_CHECKS.value
    if rap is None or not rap.edges:
        return Decision(STEP_UP, reasons=["no-path"], sig_checks=0, stage="pav")
    k = len(rap.edges)
    if k > policy.d_max:
        return Decision(STEP_UP, reasons=["depth"], sig_checks=0, stage="pav")
    pc = check_edges(rap.edges, rap.status, payment.tuple, payment.t, policy, trust)
    reasons = list(pc.reasons)
    root, end = rap.edges[0].src, rap.edges[-1].dst
    if end != payment.payee:
        reasons.append("payee-mismatch")
    beta_ok, why = verify_binding(rap.binding, payment, rap.edges[-1], trust) if end == payment.payee else (False, "")
    if why:
        reasons.append(why)
    checks = SIG_CHECKS.value - start
    if pc.ok and end == payment.payee:
        if anchor is None or root != anchor:
            # positive evidence: p is validly bound to some other entity
            return Decision(DENY, reasons=["path-to-different-entity"], root=root, principal=pc.principal,
                            sig_checks=checks, stage="pav")
        if beta_ok:
            return Decision(ALLOW, G1, [], root, pc.principal, pc.scope, sig_checks=checks, stage="pav")
    tamper = pc.tamper or any(r in TAMPER_REASONS for r in reasons)
    verdict = DENY if (policy.deny_on_tamper and tamper) else STEP_UP
    return Decision(verdict, reasons=reasons, root=root, sig_checks=checks, stage="pav")
