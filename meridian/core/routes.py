"""Committed routes and terminal subject continuity (F3); G2 verification.

A payment executes as a chain of custody transfers p = h_1 -> h_2 -> ... ->
h_n -> T. Every custodian signs a remittance commitment (payment id, next
hop, amount, validity) bound to the binding token beta; a processor signs a
payout-destination attestation naming the configured payout account. The
last link must be an IDENTITY binding, signed by the account's bank, from the
current principal's legal entity to T.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

from . import grammar
from .canon import canonical
from .decision import ALLOW, DENY, G1, G2, STEP_UP, Decision, Payment
from .edges import ID, Edge
from .ids import L4, layer
from .keys import SIG_CHECKS, KeyPair
from .pav import RAP, check_edges, pav
from .policy import Policy, TrustStore
from .status import StatusSnapshot

if TYPE_CHECKING:
    from .nonces import SpentNonces

REMIT, PAYOUT = "remit", "payout"


@dataclass(frozen=True)
class Commitment:
    kind: str
    payment_id: str
    custodian: str
    next_hop: str
    amount: int
    currency: str
    valid_until: int
    beta_digest: str
    signer_kid: str
    sig: bytes = b""

    def body(self) -> dict:
        return {
            "kind": self.kind,
            "pid": self.payment_id,
            "h": self.custodian,
            "next": self.next_hop,
            "amt": self.amount,
            "cur": self.currency,
            "exp": self.valid_until,
            "beta": self.beta_digest,
            "signer": self.signer_kid,
        }

    @classmethod
    def issue(cls, key: KeyPair, kind: str, payment: Payment, custodian: str, next_hop: str,
              beta_digest: str, amount: Optional[int] = None, ttl: int = 7 * 86400) -> "Commitment":
        c = cls(kind, payment.payment_id, custodian, next_hop,
                payment.amount if amount is None else amount, payment.currency,
                payment.t + ttl, beta_digest, key.kid)
        return cls(**{**c.__dict__, "sig": key.sign(canonical(c.body()))})

    def verify(self, trust: TrustStore) -> bool:
        pk = trust.pk(self.signer_kid)
        return pk is not None and pk.verify(self.sig, canonical(self.body()))

    def wire_size(self) -> int:
        return len(canonical(self.body())) + len(self.sig)


@dataclass
class RouteBundle:
    rap: RAP
    onward: List[Edge] = field(default_factory=list)
    commitments: List[Commitment] = field(default_factory=list)
    terminal: Optional[Edge] = None
    status: Dict[str, StatusSnapshot] = field(default_factory=dict)

    def custodians(self) -> List[str]:
        if not self.rap.edges:
            return []
        p = self.rap.edges[-1].dst
        if layer(p) == L4:
            return []
        return [p] + [e.dst for e in self.onward]

    def acceptor_of(self, custodian: str) -> Optional[str]:
        for e in list(self.rap.edges) + list(self.onward):
            if e.dst == custodian:
                return e.acceptor_kid
        return None

    def all_status(self) -> Dict[str, StatusSnapshot]:
        merged = dict(self.rap.status)
        merged.update(self.status)
        return merged

    def wire_size(self) -> int:
        n = self.rap.wire_size()
        n += sum(e.wire_size() for e in self.onward)
        n += sum(c.wire_size() for c in self.commitments)
        if self.terminal is not None:
            n += self.terminal.wire_size()
        n += sum(s.wire_size() for k, s in self.status.items() if k not in self.rap.status)
        return n

    def committed_terminal(self) -> Optional[str]:
        cs = self.custodians()
        if not cs:
            return self.rap.edges[-1].dst if self.rap.edges else None
        by_h = {c.custodian: c for c in self.commitments}
        last = by_h.get(cs[-1])
        return last.next_hop if last else None


def verify_route(bundle: Optional[RouteBundle], payment: Payment, anchor: Optional[str], policy: Policy,
                 trust: TrustStore, allow_g1: bool = False, spent: Optional["SpentNonces"] = None) -> Decision:
    """Verifiable discharge: ALLOW at G2 only with a committed route whose
    terminal account is bound to the current principal. With a ``spent`` store,
    an ALLOW claims the binding token and a token already claimed is refused;
    a decision that is not ALLOW claims nothing."""
    d = _verify_route(bundle, payment, anchor, policy, trust, allow_g1)
    if spent is not None and d.verdict == ALLOW and bundle is not None and bundle.rap.binding is not None:
        if not spent.claim(bundle.rap.binding, payment.t):
            return Decision(DENY if policy.deny_on_tamper else STEP_UP, G1, ["nonce-spent"], d.root, d.principal,
                            sig_checks=d.sig_checks, stage="route")
    return d


def _verify_route(bundle: Optional[RouteBundle], payment: Payment, anchor: Optional[str], policy: Policy,
                  trust: TrustStore, allow_g1: bool) -> Decision:
    if bundle is None:
        return Decision(STEP_UP, reasons=["no-path"], stage="route")
    start = SIG_CHECKS.value
    d = pav(bundle.rap, payment, anchor, policy, trust)
    if d.verdict != ALLOW:
        d.stage = "route/pav"
        return d
    status = bundle.all_status()
    reasons: List[str] = []
    snap_ok: Dict[str, bool] = {}

    # Onward authority edges p -> h_2 -> ... -> h_n
    if bundle.onward:
        if bundle.onward[0].src != payment.payee:
            reasons.append("chain-break")
        else:
            oc = check_edges(bundle.onward, status, payment.tuple, payment.t,
                             Policy(**{**policy.__dict__, "grammar": False}), trust, snap_ok=snap_ok)
            if not oc.ok:
                reasons.extend(oc.reasons)
            elif policy.use_scope_meet and not d.scope.meet(oc.scope).contains(payment.tuple):
                reasons.append("scope")
    if reasons:
        tamper = any(r in ("chain-break", "sig-authorize", "sig-accept") for r in reasons)
        return Decision(DENY if tamper and policy.deny_on_tamper else STEP_UP, G1, reasons, d.root,
                        d.principal, sig_checks=SIG_CHECKS.value - start, stage="route")

    custodians = bundle.custodians()
    if not custodians:
        # p itself is the terminal account (account-to-account, direct wallet)
        g = grammar.run(bundle.rap.edges, require_terminal=True)
        if not g.ok:
            return Decision(STEP_UP, G1, ["grammar:" + g.reason], d.root, d.principal,
                            sig_checks=SIG_CHECKS.value - start, stage="route")
        return Decision(ALLOW, G2, [], d.root, g.principal, d.scope, terminal=payment.payee,
                        sig_checks=SIG_CHECKS.value - start, stage="route")

    # Commitments from every custodian
    by_h: Dict[str, Commitment] = {}
    for c in bundle.commitments:
        prev = by_h.setdefault(c.custodian, c)
        if prev is not c and prev.payment_id == c.payment_id and prev.next_hop != c.next_hop:
            return Decision(DENY, G1, ["conflicting-commitments"], d.root,
                            sig_checks=SIG_CHECKS.value - start, stage="route")
    missing = [h for h in custodians if h not in by_h]
    if missing:
        verdict = ALLOW if allow_g1 else STEP_UP
        return Decision(verdict, G1, ["no-commitment:" + missing[0]], d.root, d.principal, d.scope,
                        sig_checks=SIG_CHECKS.value - start, stage="route")
    beta_digest = bundle.rap.binding.digest
    terminal_acct = None
    for i, h in enumerate(custodians):
        c = by_h[h]
        if c.signer_kid != bundle.acceptor_of(h) or not c.verify(trust):
            return Decision(DENY if policy.deny_on_tamper else STEP_UP, G1, ["commitment-sig"], d.root,
                            sig_checks=SIG_CHECKS.value - start, stage="route")
        if c.payment_id != payment.payment_id or c.beta_digest != beta_digest or c.valid_until < payment.t:
            return Decision(STEP_UP, G1, ["commitment-binding"], d.root,
                            sig_checks=SIG_CHECKS.value - start, stage="route")
        # the commitment must cover exactly this payment: a smaller amount would
        # let the custodian forward less without a breach (verify_certificate
        # compares against the committed amount), and a different currency is
        # a different obligation
        if c.amount != payment.amount or c.currency != payment.currency:
            return Decision(STEP_UP, G1, ["commitment-amount" if c.amount != payment.amount else "commitment-currency"],
                            d.root, sig_checks=SIG_CHECKS.value - start, stage="route")
        if i + 1 < len(custodians):
            if c.next_hop != custodians[i + 1]:
                # the custodian has committed to send the money somewhere the
                # presented route does not authorise
                return Decision(DENY, G1, ["commitment-off-route"], d.root,
                                sig_checks=SIG_CHECKS.value - start, stage="route")
        else:
            terminal_acct = c.next_hop

    # Terminal subject continuity
    term = bundle.terminal
    if term is None:
        return Decision(STEP_UP, G1, ["no-terminal-binding"], d.root, d.principal,
                        sig_checks=SIG_CHECKS.value - start, stage="route")
    if term.etype != ID or term.dst != terminal_acct or layer(term.dst) != L4:
        return Decision(DENY, G1, ["terminal-mismatch"], d.root,
                        sig_checks=SIG_CHECKS.value - start, stage="route")
    tc = check_edges([term], status, payment.tuple, payment.t,
                     Policy(**{**policy.__dict__, "grammar": False}), trust, snap_ok=snap_ok)
    if not tc.ok:
        tamper = any(r in ("sig-authorize", "sig-accept") for r in tc.reasons)
        return Decision(DENY if tamper and policy.deny_on_tamper else STEP_UP, G1, tc.reasons, d.root,
                        sig_checks=SIG_CHECKS.value - start, stage="route")
    word = list(bundle.rap.edges) + list(bundle.onward) + [term]
    g = grammar.run(word, require_terminal=True)
    if not g.ok:
        # a chain whose links are each valid but refer to different subjects
        verdict = DENY if "subject" in g.reason or "different principal" in g.reason else STEP_UP
        return Decision(verdict, G1, ["grammar:" + g.reason], d.root, g.principal,
                        sig_checks=SIG_CHECKS.value - start, stage="route")
    return Decision(ALLOW, G2, [], d.root, g.principal, d.scope, terminal=terminal_acct,
                    sig_checks=SIG_CHECKS.value - start, stage="route")
