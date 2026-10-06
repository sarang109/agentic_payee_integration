from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .scope import PaymentTuple, Scope

ALLOW, DENY, STEP_UP = "ALLOW", "DENY", "STEP-UP"

# Payee-integrity levels (F1)
G_NONE, G0, G1, G2, G3, G4 = -1, 0, 1, 2, 3, 4


@dataclass(frozen=True)
class Payment:
    """pi = (b*, p, r, c, a, m, g, t) plus checkout context."""

    payment_id: str
    payee: str
    rail: str
    currency: str
    amount: int
    mcc: str
    geo: str
    t: int
    cart_digest: str
    nonce: str

    @property
    def tuple(self) -> PaymentTuple:
        return PaymentTuple(self.rail, self.currency, self.amount, self.mcc, self.geo)


@dataclass
class Decision:
    verdict: str
    level: int = G_NONE
    reasons: List[str] = field(default_factory=list)
    root: Optional[str] = None
    principal: Optional[str] = None
    scope: Optional[Scope] = None
    terminal: Optional[str] = None
    sig_checks: int = 0
    stage: str = ""

    @property
    def allowed(self) -> bool:
        return self.verdict == ALLOW

    def to_json(self) -> dict:
        return {
            "verdict": self.verdict,
            "level": self.level,
            "reasons": list(self.reasons),
            "root": self.root,
            "principal": self.principal,
            "terminal": self.terminal,
            "sig_checks": self.sig_checks,
            "stage": self.stage,
        }
