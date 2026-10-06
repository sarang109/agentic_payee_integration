"""Receiving-authority edges (Definition 1) with legal edge types (F2).

An edge e = <u, v, iota_u, iota_v, sigma, [t_a, t_b], s> states that u
authorises v to receive funds on u's behalf within scope sigma during the
validity window; s points into a revocation status list. iota_u is the
authorisation signature (made by the issuer class that may vouch for this
transition, see policy.py) and iota_v the acceptance signature by v's
operator.

Edge types:
    ID    namespace binding (brand->entity, entity->account)
    AG    agency: v collects for u, accepts the duty to remit
    SUB   subagency: v's agent collects for v (requires delegate flag upstream)
    ASG   assignment: u transfers the receivable, v becomes principal
    CUS   custody: v holds funds until condition kappa is met
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

from .canon import canonical, digest
from .keys import KeyPair, PublicKey
from .scope import Scope

ID, AG, SUB, ASG, CUS = "ID", "AG", "SUB", "ASG", "CUS"
EDGE_TYPES = (ID, AG, SUB, ASG, CUS)


@dataclass(frozen=True)
class StatusRef:
    list_id: str
    index: int

    def to_json(self) -> dict:
        return {"list": self.list_id, "idx": self.index}


@dataclass(frozen=True)
class Edge:
    etype: str
    src: str
    dst: str
    scope: Scope
    valid_from: int
    valid_until: int
    status: StatusRef
    issuer_kid: str
    issuer_class: str
    acceptor_kid: Optional[str]
    delegate: bool = False
    condition: Optional[str] = None
    subject: Optional[str] = None
    issued_at: int = 0
    nonce: str = ""
    sig_u: bytes = field(default=b"", compare=False)
    sig_v: bytes = field(default=b"", compare=False)

    def payload(self) -> dict:
        return {
            "type": self.etype,
            "u": self.src,
            "v": self.dst,
            "scope": self.scope.to_json(),
            "nbf": self.valid_from,
            "exp": self.valid_until,
            "status": self.status.to_json(),
            "iss": self.issuer_kid,
            "iss_class": self.issuer_class,
            "acc": self.acceptor_kid,
            "delegate": self.delegate,
            "kappa": self.condition,
            "subject": self.subject,
            "iat": self.issued_at,
            "nonce": self.nonce,
        }

    @property
    def eid(self) -> str:
        return "e_" + digest(self.payload())[:24]

    def signing_input(self, role: str) -> bytes:
        return canonical({"role": role, "edge": self.payload()})

    def sign_authorize(self, key: KeyPair) -> "Edge":
        return replace(self, sig_u=key.sign(self.signing_input("authorize")))

    def sign_accept(self, key: KeyPair) -> "Edge":
        return replace(self, sig_v=key.sign(self.signing_input("accept")))

    def verify_authorize(self, pk: PublicKey) -> bool:
        return bool(self.sig_u) and pk.verify(self.sig_u, self.signing_input("authorize"))

    def verify_accept(self, pk: PublicKey) -> bool:
        return bool(self.sig_v) and pk.verify(self.sig_v, self.signing_input("accept"))

    def valid_at(self, t: int) -> bool:
        return self.valid_from <= t <= self.valid_until

    def wire_size(self) -> int:
        return len(canonical(self.payload())) + len(self.sig_u) + len(self.sig_v)
