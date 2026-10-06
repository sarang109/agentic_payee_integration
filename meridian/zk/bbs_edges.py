"""Algorithm 5 (BBS instantiation): edges as BBS credentials with selective
disclosure (draft-irtf-cfrg-bbs-signatures, BLS12-381-SHA-256).

Each edge is signed as a vector of messages. In a presentation the holder
discloses, per edge, the edge type, the scope fields and validity, the link
tags of its endpoints, and the raw identifier only for the anchored brand
(first edge) and the payee (last edge). Link tags are salted hashes chosen
by each node owner, so intermediaries stay hidden from the verifier but the
tags are stable across payments: this variant is lighter than the SNARK and
hides fewer relations (tags are linkable).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from ..core.edges import Edge
from ..core.scope import PaymentTuple, Scope, meet_all
from .worker import ZKWorker

FIELDS = ["type", "src", "dst", "src_tag", "dst_tag", "scope", "nbf", "exp", "status", "delegate", "subject"]
I = {k: i for i, k in enumerate(FIELDS)}


def link_tag(node: str, salt: bytes) -> str:
    return hashlib.sha256(b"meridian-link|" + salt + node.encode()).hexdigest()


def _msgs(e: Edge, salts: Dict[str, bytes]) -> List[bytes]:
    vals = {
        "type": e.etype, "src": e.src, "dst": e.dst,
        "src_tag": link_tag(e.src, salts[e.src]), "dst_tag": link_tag(e.dst, salts[e.dst]),
        "scope": json.dumps(e.scope.to_json(), sort_keys=True), "nbf": str(e.valid_from), "exp": str(e.valid_until),
        "status": f"{e.status.list_id}:{e.status.index}", "delegate": str(e.delegate), "subject": e.subject or "",
    }
    return [vals[k].encode() for k in FIELDS]


@dataclass
class BBSIssuerKey:
    sk: str
    pk: str


@dataclass
class BBSCredential:
    edge: Edge
    messages: List[bytes]
    sig: str
    issuer_pk: str


@dataclass
class BBSPresentation:
    proofs: List[Tuple[str, List[int], List[bytes], str]]  # (proof, disclosed idx, disclosed msgs, issuer pk)
    derive_ms: float
    bytes: int


class BBSEdges:
    def __init__(self, worker: ZKWorker) -> None:
        self.w = worker
        self.keys: Dict[str, BBSIssuerKey] = {}

    def issuer_key(self, issuer_kid: str) -> BBSIssuerKey:
        if issuer_kid not in self.keys:
            seed = hashlib.sha256(b"bbs-test-key|" + issuer_kid.encode()).hexdigest()
            r = self.w.call("bbs_keygen", seed=seed)
            self.keys[issuer_kid] = BBSIssuerKey(r["sk"], r["pk"])
        return self.keys[issuer_kid]

    def issue(self, e: Edge, salts: Dict[str, bytes]) -> BBSCredential:
        k = self.issuer_key(e.issuer_kid)
        msgs = _msgs(e, salts)
        r = self.w.call("bbs_sign", sk=k.sk, pk=k.pk, header="", messages=[m.hex() for m in msgs])
        return BBSCredential(e, msgs, r["sig"], k.pk)

    def present(self, creds: Sequence[BBSCredential], nonce: bytes) -> BBSPresentation:
        out = []
        total_ms = 0.0
        size = 0
        n = len(creds)
        for i, c in enumerate(creds):
            disclose = ["type", "src_tag", "dst_tag", "scope", "nbf", "exp", "status", "delegate"]
            if i == 0:
                disclose.append("src")
            if i == n - 1:
                disclose.append("dst")
            idx = sorted(I[k] for k in disclose)
            r = self.w.call("bbs_derive", pk=c.issuer_pk, sig=c.sig, header="",
                            messages=[m.hex() for m in c.messages], ph=nonce.hex(), disclosed=idx)
            total_ms += r["ms"]
            size += r["bytes"]
            out.append((r["proof"], idx, [c.messages[j] for j in idx], c.issuer_pk))
        return BBSPresentation(out, total_ms, size)

    def verify(self, pres: BBSPresentation, anchor: str, payee: str, t: PaymentTuple, now: int,
               nonce: bytes, trusted_pks: set) -> Tuple[bool, float, str]:
        total = 0.0
        prev_dst_tag = None
        scopes = []
        for i, (proof, idx, msgs, pk) in enumerate(pres.proofs):
            if pk not in trusted_pks:
                return False, total, "untrusted-issuer"
            r = self.w.call("bbs_verify", pk=pk, proof=proof, header="", ph=nonce.hex(),
                            disclosedMessages=[m.hex() for m in msgs], disclosed=idx)
            total += r["ms"]
            if not r["ok"]:
                return False, total, "proof"
            d = {FIELDS[j]: m.decode() for j, m in zip(idx, msgs)}
            if i == 0 and d.get("src") != anchor:
                return False, total, "anchor"
            if i == len(pres.proofs) - 1 and d.get("dst") != payee:
                return False, total, "payee"
            if prev_dst_tag is not None and d["src_tag"] != prev_dst_tag:
                return False, total, "chain"
            prev_dst_tag = d["dst_tag"]
            if not int(d["nbf"]) <= now <= int(d["exp"]):
                return False, total, "expired"
            scopes.append(Scope.from_json(json.loads(d["scope"])))
        if not meet_all(scopes).contains(t):
            return False, total, "scope"
        return True, total, ""


def new_salt() -> bytes:
    return os.urandom(16)


__all__ = ["BBSEdges", "BBSCredential", "BBSPresentation", "link_tag", "new_salt"]
