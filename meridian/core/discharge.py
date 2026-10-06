"""Post-authorization evidence and attributable discharge (Theorem 2).

TransferRecord     a custodian's signed record of an onward transfer (G3)
CreditConfirmation the terminal account's bank or chain confirming credit (G4)
BreachCertificate  a commitment plus a contradicting transfer record signed by
                   the same custodian; anyone holding the trust store can
                   check it, and it names the custodian that deviated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .canon import canonical
from .keys import KeyPair
from .policy import TrustStore
from .routes import Commitment, RouteBundle


@dataclass(frozen=True)
class TransferRecord:
    payment_id: str
    custodian: str
    to: str
    amount: int
    t: int
    signer_kid: str
    sig: bytes = b""

    def body(self) -> dict:
        return {"pid": self.payment_id, "h": self.custodian, "to": self.to, "amt": self.amount,
                "t": self.t, "signer": self.signer_kid}

    @classmethod
    def issue(cls, key: KeyPair, payment_id: str, custodian: str, to: str, amount: int, t: int) -> "TransferRecord":
        r = cls(payment_id, custodian, to, amount, t, key.kid)
        return cls(**{**r.__dict__, "sig": key.sign(canonical(r.body()))})

    def verify(self, trust: TrustStore) -> bool:
        pk = trust.pk(self.signer_kid)
        return pk is not None and pk.verify(self.sig, canonical(self.body()))


@dataclass(frozen=True)
class CreditConfirmation:
    payment_id: str
    account: str
    amount: int
    t: int
    signer_kid: str
    sig: bytes = b""

    def body(self) -> dict:
        return {"pid": self.payment_id, "acct": self.account, "amt": self.amount, "t": self.t,
                "signer": self.signer_kid}

    @classmethod
    def issue(cls, key: KeyPair, payment_id: str, account: str, amount: int, t: int) -> "CreditConfirmation":
        r = cls(payment_id, account, amount, t, key.kid)
        return cls(**{**r.__dict__, "sig": key.sign(canonical(r.body()))})

    def verify(self, trust: TrustStore) -> bool:
        pk = trust.pk(self.signer_kid)
        return pk is not None and pk.verify(self.sig, canonical(self.body()))


@dataclass(frozen=True)
class BreachCertificate:
    commitment: Commitment
    transfer: TransferRecord

    @property
    def custodian(self) -> str:
        return self.commitment.custodian

    @property
    def signer(self) -> str:
        return self.commitment.signer_kid

    def to_json(self) -> dict:
        return {"commitment": self.commitment.body(), "commitment_sig": self.commitment.sig.hex(),
                "transfer": self.transfer.body(), "transfer_sig": self.transfer.sig.hex()}


def verify_certificate(cert: BreachCertificate, trust: TrustStore) -> bool:
    c, r = cert.commitment, cert.transfer
    if c.signer_kid != r.signer_kid:
        return False
    if c.payment_id != r.payment_id or c.custodian != r.custodian:
        return False
    if not (c.verify(trust) and r.verify(trust)):
        return False
    return r.to != c.next_hop or r.amount < c.amount


def find_breach(bundle: RouteBundle, transfers: List[TransferRecord], trust: TrustStore) -> Optional[BreachCertificate]:
    """Walk the committed route; the first hop whose realised transfer differs
    from its commitment yields the certificate."""
    by_h = {c.custodian: c for c in bundle.commitments}
    recs = {}
    for r in transfers:
        if r.verify(trust):
            recs.setdefault(r.custodian, r)
    for h in bundle.custodians():
        c = by_h.get(h)
        r = recs.get(h)
        if c is None or r is None:
            continue
        cert = BreachCertificate(c, r)
        if verify_certificate(cert, trust):
            return cert
    return None
