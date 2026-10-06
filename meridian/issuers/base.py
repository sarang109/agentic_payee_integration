"""Mock issuers, one per layer transition.

Each issuer turns a check that already happens today into a portable edge:
domain control and mark verification (L0->L1), vLEI role credentials (L1),
platform onboarding (L1->L2), PSP / payfac KYB (L2->L3), payout-account and
Verification-of-Payee checks by banks (L1->L4).
"""

from __future__ import annotations

import itertools
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from ..core.canon import b64u, sha256
from ..core.discharge import CreditConfirmation, TransferRecord
from ..core.edges import Edge
from ..core.keys import ED25519, KeyPair
from ..core.pav import BindingToken
from ..core.decision import Payment
from ..core.policy import (ACQUIRER, BANK, DOMAIN_VERIFIER, ESCROW, PLATFORM, PSP, VLEI_QVI, RoleCredential,
                           TrustStore)
from ..core.routes import PAYOUT, REMIT, Commitment
from ..core.scope import Scope
from ..core.status import StatusList, StatusRegistry

_counter = itertools.count()


def _seed(name: str) -> bytes:
    return name.encode()


@dataclass
class LegalEntity:
    name: str
    lei: str
    rep: KeyPair
    jurisdiction: str = "US"
    registered_at: int = 0

    @property
    def lei_id(self) -> str:
        return f"lei:{self.lei}"


@dataclass
class Issuer:
    name: str
    cls: str
    namespaces: Set[str]
    status_registry: StatusRegistry
    deterministic: bool = True
    key: KeyPair = None
    status_list: StatusList = None
    issued: List[Edge] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.key is None:
            self.key = KeyPair.from_seed(_seed(f"{self.cls}:{self.name}")) if self.deterministic else KeyPair()
        if self.status_list is None:
            self.status_list = self.status_registry.create(f"sl:{self.cls}:{self.name}", self.key, capacity=1 << 16)

    def register(self, trust: TrustStore) -> None:
        trust.add_root(self.key, self.cls, self.namespaces, self.name)

    def issue(self, etype: str, src: str, dst: str, scope: Scope, nbf: int, exp: int, acceptor: Optional[KeyPair],
              delegate: bool = False, condition: Optional[str] = None, subject: Optional[str] = None,
              issued_at: Optional[int] = None, signing_key: Optional[KeyPair] = None) -> Edge:
        """Issue an edge. ``signing_key`` lets an entity rep authorise an edge
        whose status entry this issuer still hosts (e.g. L1->L2 edges)."""
        signer = signing_key or self.key
        e = Edge(etype, src, dst, scope, nbf, exp, self.status_list.allocate(), signer.kid, self.cls,
                 acceptor.kid if acceptor else None, delegate, condition, subject,
                 nbf if issued_at is None else issued_at, nonce=str(next(_counter)))
        e = e.sign_authorize(signer)
        if acceptor is not None:
            e = e.sign_accept(acceptor)
        self.issued.append(e)
        return e

    def revoke(self, e: Edge, t: int) -> None:
        sl = self.status_registry.lists[e.status.list_id]
        sl.revoke(e.status.index, t)


class DomainVerifier(Issuer):
    """ACME-style DNS-01 challenge plus verified-mark check. A careless
    verifier skips the DNS check (used for A9)."""

    def __init__(self, name: str, status_registry: StatusRegistry, careless: bool = False):
        super().__init__(name, DOMAIN_VERIFIER, {"*"}, status_registry)
        self.careless = careless
        self.pending: Dict[str, str] = {}

    def challenge(self, domain: str, account_key: KeyPair) -> str:
        token = b64u(secrets.token_bytes(16))
        thumb = b64u(sha256(account_key.public.raw))
        value = b64u(sha256(f"{token}.{thumb}".encode()))
        self.pending[domain] = value
        return value

    def check(self, domain: str, dns: Dict[str, List[str]]) -> bool:
        if self.careless:
            return True
        want = self.pending.get(domain)
        return want is not None and want in dns.get(f"_meridian-challenge.{domain}", [])

    def bind(self, domain: str, entity: LegalEntity, dns: Dict[str, List[str]], nbf: int, exp: int,
             scope: Optional[Scope] = None) -> Optional[Edge]:
        if not self.check(domain, dns):
            return None
        return self.issue("ID", f"brand:{domain}", entity.lei_id, scope or Scope.top(), nbf, exp, entity.rep)


class QVI(Issuer):
    def __init__(self, name: str, status_registry: StatusRegistry):
        super().__init__(name, VLEI_QVI, {"*"}, status_registry)

    def role_credential(self, entity: LegalEntity, exp: int) -> RoleCredential:
        return RoleCredential(entity.lei, entity.rep.public, self.key.kid, exp).sign(self.key)


class Operator(Issuer):
    """Platforms, PSPs, acquirers, escrow operators: they run a namespace of
    L2/L3 identifiers, accept edges into it and sign commitments, binding
    tokens and transfer records for the accounts they operate."""

    def __init__(self, name: str, cls: str, namespaces: Set[str], status_registry: StatusRegistry):
        super().__init__(name, cls, namespaces, status_registry)
        self._accounts = itertools.count(1)

    def new_account(self, prefix: str = "acct", ns: Optional[str] = None) -> str:
        if ns is None:
            procs = sorted(n for n in self.namespaces if n.startswith("proc:"))
            ns = procs[0] if procs else sorted(self.namespaces)[0]
        return f"{ns}/{prefix}_{next(self._accounts):06d}"

    def binding_token(self, payment: Payment, ttl: int = 900) -> BindingToken:
        return BindingToken.issue(self.key, payment, ttl)

    def commit(self, payment: Payment, custodian: str, next_hop: str, beta_digest: str,
               kind: str = REMIT, amount: Optional[int] = None) -> Commitment:
        return Commitment.issue(self.key, kind, payment, custodian, next_hop, beta_digest, amount)

    def payout_attestation(self, payment: Payment, custodian: str, payout_acct: str, beta_digest: str) -> Commitment:
        return Commitment.issue(self.key, PAYOUT, payment, custodian, payout_acct, beta_digest)

    def transfer_record(self, payment_id: str, custodian: str, to: str, amount: int, t: int) -> TransferRecord:
        return TransferRecord.issue(self.key, payment_id, custodian, to, amount, t)


def Platform(name: str, status_registry: StatusRegistry, extra_ns: Set[str] = frozenset()) -> Operator:
    return Operator(name, PLATFORM, {f"mor:{name}", f"proc:{name}"} | set(extra_ns), status_registry)


def PSPOperator(name: str, status_registry: StatusRegistry) -> Operator:
    return Operator(name, PSP, {f"proc:{name}"}, status_registry)


def Acquirer(name: str, status_registry: StatusRegistry) -> Operator:
    return Operator(name, ACQUIRER, {f"proc:{name}"}, status_registry)


def EscrowOperator(name: str, status_registry: StatusRegistry) -> Operator:
    return Operator(name, ESCROW, {f"proc:{name}"}, status_registry)


class Bank(Operator):
    """Holds accounts, runs Verification of Payee against names or LEIs and
    signs terminal bindings (entity -> account) and credit confirmations."""

    def __init__(self, name: str, status_registry: StatusRegistry):
        super().__init__(name, BANK, {f"acct:{name}"}, status_registry)
        self.holders: Dict[str, LegalEntity] = {}
        self.holder_names: Dict[str, str] = {}

    def open_account(self, holder: LegalEntity, iban: Optional[str] = None) -> str:
        iban = iban or f"XX{secrets.randbelow(10**18):018d}"
        acct = f"acct:{self.name}/{b64u(sha256((self.name + iban).encode()))[:22]}"
        self.holders[acct] = holder
        self.holder_names[acct] = holder.name
        return acct

    def vop(self, acct: str, name: Optional[str] = None, lei: Optional[str] = None) -> str:
        """EPC VoP-style answer: MATCH, CLOSE_MATCH, NO_MATCH or NOT_POSSIBLE."""
        h = self.holders.get(acct)
        if h is None:
            return "NOT_POSSIBLE"
        if lei is not None:
            return "MATCH" if lei == h.lei else "NO_MATCH"
        if name is None:
            return "NOT_POSSIBLE"
        a, b = name.strip().lower(), h.name.strip().lower()
        if a == b:
            return "MATCH"
        if a.replace(" ", "") == b.replace(" ", "") or a in b or b in a:
            return "CLOSE_MATCH"
        return "NO_MATCH"

    def terminal_binding(self, acct: str, nbf: int, exp: int, scope: Optional[Scope] = None) -> Edge:
        holder = self.holders[acct]
        return self.issue("ID", holder.lei_id, acct, scope or Scope.top(), nbf, exp, holder.rep)

    def credit(self, payment_id: str, acct: str, amount: int, t: int) -> CreditConfirmation:
        return CreditConfirmation.issue(self.key, payment_id, acct, amount, t)


def make_entity(name: str, lei: str, jurisdiction: str = "US", registered_at: int = 0,
                deterministic: bool = True, alg: str = ED25519) -> LegalEntity:
    rep = KeyPair.from_seed(_seed(f"rep:{lei}"), alg) if deterministic else KeyPair(alg)
    return LegalEntity(name, lei, rep, jurisdiction, registered_at)
