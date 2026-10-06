"""AP2 (v0.2 SDK types, pinned in data/upstream/PINS.txt) with the MERIDIAN
extension.

The extension adds ``receiving_authority`` to the payment mandate: the digest
of the RAP / route bundle and of the payee binding token beta. The credential
provider runs MERIDIAN before it signs the mandate or releases the
instrument, and the mandate's payee.id must be the rail payee identifier p
that the RAP proves.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import List, Optional

from ..core.canon import b64u, digest, sha256
from ..core.decision import DENY, STEP_UP, Decision, Payment
from ..core.policy import Policy, TrustStore
from ..core.routes import RouteBundle, verify_route


@dataclass(frozen=True)
class Merchant:
    id: str
    name: str
    website: Optional[str] = None


@dataclass(frozen=True)
class Amount:
    currency: str
    amount: int


@dataclass(frozen=True)
class CheckoutMandate:
    checkout_jwt: str
    checkout_hash: str
    vct: str = "mandate.checkout.1"
    iat: Optional[int] = None
    exp: Optional[int] = None


@dataclass(frozen=True)
class ReceivingAuthority:
    route_digest: str
    binding_digest: str
    anchored_brand: str


@dataclass(frozen=True)
class PaymentMandate:
    transaction_id: str
    payee: Merchant
    payment_amount: Amount
    payment_instrument: dict
    vct: str = "mandate.payment.1"
    risk_data: Optional[dict] = None
    iat: Optional[int] = None
    exp: Optional[int] = None
    receiving_authority: Optional[ReceivingAuthority] = None  # MERIDIAN extension


@dataclass(frozen=True)
class AllowedPayees:
    allowed: List[Merchant]
    type: str = "payment.allowed_payees"


def checkout_hash(checkout_jwt: str) -> str:
    return b64u(sha256(checkout_jwt.encode()))


def route_digest(bundle: RouteBundle) -> str:
    return digest({
        "edges": [e.eid for e in bundle.rap.edges + bundle.onward],
        "commitments": [c.body() for c in bundle.commitments],
        "terminal": bundle.terminal.eid if bundle.terminal else None,
    })


def build_mandate(checkout_jwt: str, payment: Payment, merchant_name: str, bundle: Optional[RouteBundle],
                  anchor: str) -> PaymentMandate:
    ra = None
    if bundle is not None and bundle.rap.binding is not None:
        ra = ReceivingAuthority(route_digest(bundle), bundle.rap.binding.digest, anchor)
    return PaymentMandate(checkout_hash(checkout_jwt), Merchant(payment.payee, merchant_name),
                          Amount(payment.currency, payment.amount), {"type": "card", "token": "tok_test"},
                          iat=payment.t, exp=payment.t + 900, receiving_authority=ra)


def reference_allowed_payee_check(constraint: AllowedPayees, payee: Merchant) -> bool:
    """Payee check as reported for the AP2 reference in arXiv 2609.00060
    (an allowed payee with an empty merchant id matched any payee). Kept to
    reproduce the finding; MERIDIAN does not rely on it."""
    for a in constraint.allowed:
        if not a.id or a.id == payee.id:
            return True
    return False


def strict_allowed_payee_check(constraint: AllowedPayees, payee: Merchant) -> bool:
    return any(a.id and a.id == payee.id for a in constraint.allowed)


def meridian_check(mandate: PaymentMandate, checkout_jwt: str, payment: Payment, bundle: Optional[RouteBundle],
                   anchor: str, policy: Policy, trust: TrustStore) -> Decision:
    if mandate.transaction_id != checkout_hash(checkout_jwt):
        return Decision(DENY, reasons=["ap2-transaction-id"], stage="ap2")
    if mandate.payee.id != payment.payee:
        return Decision(DENY, reasons=["ap2-payee-not-rail-payee"], stage="ap2")
    if mandate.payment_amount != Amount(payment.currency, payment.amount):
        return Decision(DENY, reasons=["ap2-amount"], stage="ap2")
    ra = mandate.receiving_authority
    if ra is None or bundle is None:
        return Decision(STEP_UP, reasons=["ap2-no-receiving-authority"], stage="ap2")
    if ra.anchored_brand != anchor or ra.route_digest != route_digest(bundle) \
            or bundle.rap.binding is None or ra.binding_digest != bundle.rap.binding.digest:
        return Decision(DENY, reasons=["ap2-receiving-authority-mismatch"], stage="ap2")
    d = verify_route(bundle, payment, anchor, policy, trust)
    d.stage = "ap2/" + d.stage
    return d


def mutations(m: PaymentMandate) -> List[tuple]:
    """Single-field mutations used by the T4 mutation tests."""
    out = [
        ("payee.id", replace(m, payee=replace(m.payee, id=m.payee.id + "x"))),
        ("payee.id-empty", replace(m, payee=replace(m.payee, id=""))),
        ("payee.name", replace(m, payee=replace(m.payee, name=m.payee.name + " Official"))),
        ("payment_amount", replace(m, payment_amount=replace(m.payment_amount, amount=m.payment_amount.amount + 1))),
        ("transaction_id", replace(m, transaction_id=m.transaction_id[::-1])),
    ]
    if m.receiving_authority is not None:
        ra = m.receiving_authority
        out += [
            ("ra.route_digest", replace(m, receiving_authority=replace(ra, route_digest="0" * 64))),
            ("ra.binding_digest", replace(m, receiving_authority=replace(ra, binding_digest="0" * 64))),
            ("ra.anchored_brand", replace(m, receiving_authority=replace(ra, anchored_brand="brand:evil.example"))),
            ("ra.removed", replace(m, receiving_authority=None)),
        ]
    return out


def to_json(m: PaymentMandate) -> dict:
    return asdict(m)


__all__ = ["Merchant", "Amount", "CheckoutMandate", "PaymentMandate", "AllowedPayees", "ReceivingAuthority",
           "build_mandate", "meridian_check", "mutations", "reference_allowed_payee_check",
           "strict_allowed_payee_check", "to_json"]
