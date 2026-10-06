"""Algorithm 5 (Merkle-membership instantiation): private payee membership.

The log commits, per brand, to the set of admitted route summaries. A route
summary is admitted only after the log ran the same checks as the v2-core
verifier on the real edges (PAV path, committed route template, terminal
binding, probation). The payer-side verifier then sees only the brand, the
payee it is paying, a hiding commitment to the terminal account and an
ALLOW bit from a Groth16 proof.

Admission is what the SNARK statement does not cover: the circuit proves
membership and scope containment, not the signatures on the underlying
edges. Its soundness therefore rests on the log's admission check (T5).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.scope import INF, RAILS, PaymentTuple, Scope
from .worker import ZKWorker, shared

R_BN254 = 21888242871839275222246405745257275088548364400416034343698204186575808495617
DEPTH = 16

CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "CAD", "AUD", "CHF", "SEK", "BRL", "SGD", "MXN", "USDC", "PYUSD",
              "NZD", "HKD", "NOK", "DKK", "PLN", "ZAR", "KRW", "CNY", "AED", "SAR", "TRY", "IDR", "THB", "MYR",
              "PHP", "VND", "CZK", "OTHER"]
GEOS = ["US", "GB", "DE", "FR", "IN", "ES", "IT", "NL", "IE", "SE", "PL", "BE", "AT", "PT", "FI", "DK", "CA", "AU",
        "JP", "SG", "BR", "MX", "CH", "NO", "NZ", "HK", "AE", "ZA", "KR", "CN", "LU", "CZ", "GR", "HU", "RO", "BG",
        "HR", "SK", "SI", "LT", "LV", "EE", "CY", "MT", "IS", "LI", "TR", "SA", "IL", "TH", "MY", "PH", "ID", "VN",
        "AR", "CL", "CO", "PE", "EG", "NG", "KE", "PK", "BD", "OTHER"]
MCCS = ["5411", "5499", "5651", "5661", "5691", "5699", "5732", "5734", "5735", "5812", "5814", "5912", "5942",
        "5945", "5947", "5964", "5965", "5969", "5977", "5999", "4111", "4121", "4511", "4722", "4812", "4814",
        "4816", "4899", "4900", "5045", "5065", "5111", "5122", "5137", "5139", "5192", "5200", "5251", "5311",
        "5331", "5399", "5441", "5462", "5532", "5533", "5541", "5712", "5719", "5722", "5733", "5940", "5941",
        "5944", "5946", "5948", "5970", "5992", "5994", "6012", "6051", "7011", "7299", "7372", "OTHER"]

assert len(RAILS) <= 16 and len(CURRENCIES) <= 32 and len(GEOS) <= 64 and len(MCCS) <= 64


def to_field(identifier: str) -> int:
    return int.from_bytes(hashlib.sha256(identifier.encode()).digest(), "big") % R_BN254


def _index(table: List[str], v: str) -> int:
    return table.index(v) if v in table else len(table) - 1


def _mask(table: List[str], values) -> int:
    if values is None:
        return (1 << len(table)) - 1
    m = 0
    for v in values:
        m |= 1 << _index(table, v)
    return m


def scope_fields(sc: Scope) -> Dict[str, int]:
    return {
        "railsMask": _mask(list(RAILS), sc.rails),
        "curMask": _mask(CURRENCIES, sc.currencies),
        "ceiling": min(sc.ceiling, (1 << 63) - 1) if sc.ceiling != INF else (1 << 63) - 1,
        "mccMask": _mask(MCCS, sc.mccs),
        "geoMask": _mask(GEOS, sc.geos),
    }


def tuple_fields(t: PaymentTuple) -> Dict[str, int]:
    return {"rail": list(RAILS).index(t.rail), "currency": _index(CURRENCIES, t.currency), "amount": t.amount,
            "mcc": _index(MCCS, t.mcc), "geo": _index(GEOS, t.geo)}


@dataclass
class RouteSummary:
    brand: str
    payee: str
    terminal: str
    scope: Scope
    not_before: int  # admission time + probation for high-risk routes
    not_after: int
    blinding: int = field(default_factory=lambda: secrets.randbelow(R_BN254))


@dataclass
class MembershipProof:
    proof: dict
    public: List[str]
    prove_ms: float
    bytes: int


class MembershipLog:
    """Per-brand Poseidon Merkle commitments over admitted route summaries."""

    def __init__(self, worker: Optional[ZKWorker] = None) -> None:
        self.worker = worker or shared()
        self.sets: Dict[str, List[RouteSummary]] = {}
        self._leaf_cache: Dict[int, str] = {}
        self._trees: Dict[str, Tuple[str, List[dict], List[str]]] = {}

    def term_commit(self, s: RouteSummary) -> str:
        return self.worker.call("poseidon", inputs=[str(to_field(s.terminal)), str(s.blinding)])["hash"]

    def leaf(self, s: RouteSummary) -> str:
        key = id(s)
        if key in self._leaf_cache:
            return self._leaf_cache[key]
        f = scope_fields(s.scope)
        inputs = [to_field(s.brand), to_field(s.payee), int(self.term_commit(s)), f["railsMask"], f["curMask"],
                  f["ceiling"], f["mccMask"], f["geoMask"], s.not_before, s.not_after]
        h = self.worker.call("poseidon", inputs=[str(x) for x in inputs])["hash"]
        self._leaf_cache[key] = h
        return h

    def admit(self, s: RouteSummary) -> None:
        self.sets.setdefault(s.brand, []).append(s)
        self._trees.pop(s.brand, None)

    def withdraw(self, brand: str, payee: str) -> None:
        self.sets[brand] = [s for s in self.sets.get(brand, []) if s.payee != payee]
        self._trees.pop(brand, None)

    def root(self, brand: str) -> Tuple[str, List[dict], List[str]]:
        if brand not in self._trees:
            leaves = [self.leaf(s) for s in self.sets.get(brand, [])]
            if not leaves:
                t = self.worker.call("tree", leaves=["0"], depth=DEPTH)
                self._trees[brand] = (t["root"], [], [])
            else:
                t = self.worker.call("tree", leaves=leaves, depth=DEPTH)
                self._trees[brand] = (t["root"], t["paths"], leaves)
        return self._trees[brand]

    def find(self, brand: str, payee: str, t: PaymentTuple, now: int) -> Optional[int]:
        for i, s in enumerate(self.sets.get(brand, [])):
            if s.payee == payee and s.scope.contains(t) and s.not_before <= now <= s.not_after:
                return i
        return None

    def prove(self, brand: str, payee: str, t: PaymentTuple, now: int) -> Optional[Tuple[MembershipProof, str]]:
        """Prover side (merchant/PSP). Returns the proof and the public term
        commitment, or None when no admitted leaf covers the payment."""
        idx = self.find(brand, payee, t, now)
        if idx is None:
            return None
        s = self.sets[brand][idx]
        root, paths, _ = self.root(brand)
        f = scope_fields(s.scope)
        tc = self.term_commit(s)
        inp = {"root": root, "brand": str(to_field(brand)), "payee": str(to_field(payee)), "termCommit": tc,
               **{k: str(v) for k, v in tuple_fields(t).items()}, "t": str(now),
               **{k: str(v) for k, v in f.items()}, "notBefore": str(s.not_before), "notAfter": str(s.not_after),
               "pathElements": paths[idx]["elements"], "pathIndices": [str(x) for x in paths[idx]["indices"]]}
        r = self.worker.call("prove", input=inp)
        return MembershipProof(r["proof"], r["publicSignals"], r["ms"], r["bytes"]), tc

    def verify(self, brand: str, payee: str, t: PaymentTuple, now: int, proof: MembershipProof,
               term_commit: str) -> Tuple[bool, float]:
        """Verifier side: rebuild the public inputs itself so a proof for a
        different brand, payee or payment tuple cannot be replayed."""
        root, _, _ = self.root(brand)
        tf = tuple_fields(t)
        want = [root, str(to_field(brand)), str(to_field(payee)), term_commit, str(tf["rail"]), str(tf["currency"]),
                str(tf["amount"]), str(tf["mcc"]), str(tf["geo"]), str(now)]
        if [str(x) for x in proof.public] != want:
            return False, 0.0
        r = self.worker.call("verify", proof=proof.proof, publicSignals=proof.public)
        return bool(r["ok"]), float(r["ms"])
