"""Machine Payments Protocol style challenge / credential / receipt flow with
session spending limits, carrying the MERIDIAN route digest in the challenge.

Header and field names follow the HTTP 'Payment' authentication scheme
pattern (WWW-Authenticate: Payment ..., Authorization: Payment ...,
Payment-Receipt). They are provisional and must be aligned with the pinned
MPP specification before interop claims are made.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Dict, Optional

from ..core.canon import canonical, digest
from ..core.keys import KeyPair, PublicKey


def _b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(canonical(obj)).decode().rstrip("=")


def _unb64(s: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)))


def challenge(realm: str, recipient: str, amount: int, currency: str, method: str, meridian: Optional[dict]) -> str:
    req = {"amount": amount, "currency": currency, "recipient": recipient}
    if meridian:
        req["meridian"] = meridian
    return f'Payment realm="{realm}", method="{method}", intent="charge", request="{_b64(req)}"'


def parse_challenge(header: str) -> Dict[str, str]:
    body = header.split(" ", 1)[1]
    out = {}
    for part in body.split(", "):
        k, v = part.split("=", 1)
        out[k] = v.strip('"')
    out["request_obj"] = _unb64(out["request"])
    return out


@dataclass
class Session:
    session_id: str
    limit: int
    spent: int = 0
    payees: set = field(default_factory=set)


def credential(session: Session, key: KeyPair, ch: Dict[str, str]) -> Optional[str]:
    req = ch["request_obj"]
    if session.spent + req["amount"] > session.limit:
        return None
    body = {"session": session.session_id, "request_digest": digest(req), "recipient": req["recipient"],
            "amount": req["amount"]}
    sig = key.sign(canonical(body)).hex()
    session.spent += req["amount"]
    session.payees.add(req["recipient"])
    return f'Payment credential="{_b64({**body, "sig": sig})}"'


def verify_credential(header: str, pk: PublicKey) -> Optional[dict]:
    cred = _unb64(header.split('credential="', 1)[1].rstrip('"'))
    sig = bytes.fromhex(cred.pop("sig"))
    return cred if pk.verify(sig, canonical(cred)) else None


def receipt(server_key: KeyPair, cred: dict, t: int) -> str:
    body = {"session": cred["session"], "recipient": cred["recipient"], "amount": cred["amount"], "t": t}
    return _b64({**body, "sig": server_key.sign(canonical(body)).hex()})
