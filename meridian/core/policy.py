"""Trust store and typed issuance policy (Definition 3).

Allowed(e) holds only when the edge's signers match the issuer class allowed
for its layer transition:

    L0 -> L1  ID            domain-and-mark verifier;   accepted by entity rep
    L1 -> L2  AG/ASG        entity rep (vLEI role);     accepted by platform
    L1 -> L3  AG/CUS        entity rep;                 accepted by PSP/acquirer
    L2 -> L3  AG/SUB        platform or PSP;            accepted by PSP/operator
    L3 -> L3  AG/SUB/CUS    operator of source;         accepted by operator of dest
    L1 -> L1  ASG/AG        entity rep of source;       accepted by entity rep of dest
    L1 -> L4  ID            bank of the account;        accepted by entity rep
              (chain)       entity rep;                 accepted by wallet key
    L3 -> L4  ID            PSP that verified payout or the bank

Entity representatives are recognised through vLEI-style role credentials
issued by a qualified vLEI issuer (QVI).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Set, Tuple

from .canon import canonical
from .edges import AG, ASG, CUS, ID, SUB, Edge
from .ids import L0, L1, L2, L3, L4, layer, namespace
from .keys import KeyPair, PublicKey

DOMAIN_VERIFIER = "domain_verifier"
VLEI_QVI = "vlei_qvi"
ENTITY_REP = "entity_rep"
PLATFORM = "platform"
PSP = "psp"
ACQUIRER = "acquirer"
BANK = "bank"
ESCROW = "escrow"
WALLET = "wallet"

OPERATOR_CLASSES = {PLATFORM, PSP, ACQUIRER, BANK, ESCROW}


@dataclass
class RootInfo:
    kid: str
    pk: PublicKey
    cls: str
    namespaces: Set[str]
    name: str = ""


@dataclass(frozen=True)
class RoleCredential:
    """vLEI-style credential: the QVI states that rep_kid represents lei."""

    lei: str
    rep_pk: PublicKey
    qvi_kid: str
    valid_until: int
    sig: bytes = b""

    def body(self) -> dict:
        return {"lei": self.lei, "rep": self.rep_pk.kid, "rep_alg": self.rep_pk.alg,
                "qvi": self.qvi_kid, "exp": self.valid_until}

    def sign(self, qvi: KeyPair) -> "RoleCredential":
        return RoleCredential(self.lei, self.rep_pk, self.qvi_kid, self.valid_until, qvi.sign(canonical(self.body())))


class TrustStore:
    def __init__(self) -> None:
        self.roots: Dict[str, RootInfo] = {}
        self.reps: Dict[str, Tuple[PublicKey, Set[str]]] = {}
        self.wallets: Dict[str, PublicKey] = {}
        self._wallet_by_kid: Dict[str, PublicKey] = {}
        self._ns_operators: Dict[str, Set[str]] = {}

    # roots -------------------------------------------------------------
    def add_root(self, key: KeyPair | PublicKey, cls: str, namespaces: Iterable[str] = ("*",), name: str = "") -> RootInfo:
        pk = key.public if isinstance(key, KeyPair) else key
        info = RootInfo(pk.kid, pk, cls, set(namespaces), name)
        self.roots[pk.kid] = info
        for ns in info.namespaces:
            self._ns_operators.setdefault(ns, set()).add(pk.kid)
        return info

    def remove_root(self, kid: str) -> None:
        info = self.roots.pop(kid, None)
        if info:
            for ns in info.namespaces:
                self._ns_operators.get(ns, set()).discard(kid)

    def add_role_credential(self, cred: RoleCredential, now: int = 0) -> bool:
        qvi = self.roots.get(cred.qvi_kid)
        if qvi is None or qvi.cls != VLEI_QVI:
            return False
        if not qvi.pk.verify(cred.sig, canonical(cred.body())) or cred.valid_until < now:
            return False
        pk, leis = self.reps.get(cred.rep_pk.kid, (cred.rep_pk, set()))
        leis.add(cred.lei)
        self.reps[cred.rep_pk.kid] = (pk, leis)
        return True

    def add_wallet(self, address_id: str, pk: PublicKey) -> None:
        """Self-certifying wallet keys: the address is derived from the key."""
        self.wallets[address_id] = pk
        self._wallet_by_kid[pk.kid] = pk

    # lookups -----------------------------------------------------------
    def pk(self, kid: Optional[str]) -> Optional[PublicKey]:
        if kid is None:
            return None
        if kid in self.roots:
            return self.roots[kid].pk
        if kid in self.reps:
            return self.reps[kid][0]
        return self._wallet_by_kid.get(kid)

    def cls_of(self, kid: Optional[str]) -> Optional[str]:
        if kid in self.roots:
            return self.roots[kid].cls
        if kid in self.reps:
            return ENTITY_REP
        return None

    def is_class(self, kid: Optional[str], cls: str) -> bool:
        return kid is not None and kid in self.roots and self.roots[kid].cls == cls

    def is_rep(self, kid: Optional[str], lei_id: str) -> bool:
        if kid is None or kid not in self.reps:
            return False
        lei = lei_id.split(":", 1)[1] if lei_id.startswith("lei:") else lei_id
        return lei in self.reps[kid][1]

    def is_operator(self, kid: Optional[str], identifier: str) -> bool:
        if kid is None or kid not in self.roots:
            return False
        info = self.roots[kid]
        if info.cls not in OPERATOR_CLASSES:
            return False
        return namespace(identifier) in info.namespaces

    def is_wallet_key(self, kid: Optional[str], identifier: str) -> bool:
        pk = self.wallets.get(identifier)
        return pk is not None and pk.kid == kid

    def operators_of(self, identifier: str) -> Set[str]:
        return set(self._ns_operators.get(namespace(identifier), set()))


@dataclass
class Policy:
    d_max: int = 6
    rho: int = 300  # status freshness bound, seconds
    require_acceptance: bool = True  # bilateral rule (ablation 1)
    use_scope_meet: bool = True  # ablation 2
    grammar: bool = True  # v2 core route grammar
    deny_on_tamper: bool = True
    allowed_rules: Optional[Set[Tuple[int, int, str]]] = field(default=None)


def _issuer_ok(e: Edge, ts: TrustStore) -> bool:
    lu, lv = layer(e.src), layer(e.dst)
    k = e.issuer_kid
    t = e.etype
    if (lu, lv) == (L0, L1):
        return t == ID and ts.is_class(k, DOMAIN_VERIFIER)
    if (lu, lv) == (L1, L2):
        return t in (AG, ASG) and ts.is_rep(k, e.src)
    if (lu, lv) == (L1, L3):
        return t in (AG, CUS) and ts.is_rep(k, e.src)
    if (lu, lv) == (L2, L3):
        return t in (AG, SUB) and (ts.is_operator(k, e.src) or ts.is_operator(k, e.dst))
    if (lu, lv) == (L3, L3):
        return t in (AG, SUB, CUS) and ts.is_operator(k, e.src)
    if (lu, lv) == (L1, L1):
        return t in (ASG, AG) and ts.is_rep(k, e.src)
    if (lu, lv) == (L1, L4):
        if t != ID:
            return False
        if e.dst.startswith("chain:"):
            return ts.is_rep(k, e.src)
        return ts.is_class(k, BANK) and ts.is_operator(k, e.dst)
    if (lu, lv) == (L3, L4):
        return t == ID and (ts.is_operator(k, e.src) or (ts.is_class(k, BANK) and ts.is_operator(k, e.dst)))
    return False


def _acceptor_ok(e: Edge, ts: TrustStore) -> bool:
    lu, lv = layer(e.src), layer(e.dst)
    k = e.acceptor_kid
    if lv == L1:
        return ts.is_rep(k, e.dst)
    if lv in (L2, L3):
        return ts.is_operator(k, e.dst)
    if lv == L4:
        if e.dst.startswith("chain:"):
            return ts.is_wallet_key(k, e.dst)
        if lu == L1:
            return ts.is_rep(k, e.src)
        return ts.is_operator(k, e.dst) or ts.is_operator(k, e.src)
    return False


def allowed(e: Edge, ts: TrustStore, policy: Policy) -> Tuple[bool, str]:
    """Allowed(e) plus signature checks. Returns (ok, reason)."""
    if not _issuer_ok(e, ts):
        return False, "issuer-class"
    pk_u = ts.pk(e.issuer_kid)
    if pk_u is None or not e.verify_authorize(pk_u):
        return False, "sig-authorize"
    if policy.require_acceptance:
        if not _acceptor_ok(e, ts):
            return False, "acceptor-class"
        pk_v = ts.pk(e.acceptor_kid)
        if pk_v is None or not e.verify_accept(pk_v):
            return False, "sig-accept"
    return True, ""
