"""Encodings of receiving-authority edges as W3C VC 2.0 (JSON, detached
signature proofs) and as SD-JWT VC compact tokens.

Only used for interoperability and for reporting realistic wire sizes; the
verifier works on the native Edge objects.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

from .canon import b64u, canonical, sha256
from .edges import Edge
from .keys import KeyPair

VC_CONTEXT = ["https://www.w3.org/ns/credentials/v2", "https://meridian.example/ns/receiving-authority/v1"]


def edge_to_vc(e: Edge) -> dict:
    p = e.payload()
    return {
        "@context": VC_CONTEXT,
        "type": ["VerifiableCredential", "ReceivingAuthorityCredential"],
        "id": f"urn:meridian:edge:{e.eid}",
        "issuer": f"urn:meridian:key:{e.issuer_kid}",
        "validFrom": p["nbf"],
        "validUntil": p["exp"],
        "credentialStatus": {
            "type": "BitstringStatusListEntry",
            "statusPurpose": "revocation",
            "statusListCredential": f"urn:meridian:status:{e.status.list_id}",
            "statusListIndex": str(e.status.index),
        },
        "credentialSubject": {
            "id": e.dst,
            "edgeType": e.etype,
            "authorizedBy": e.src,
            "scope": p["scope"],
            "delegate": e.delegate,
            "condition": e.condition,
            "subject": e.subject,
        },
        "proof": [
            {"type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "proofPurpose": "assertionMethod",
             "verificationMethod": f"urn:meridian:key:{e.issuer_kid}", "proofValue": "u" + b64u(e.sig_u)},
            {"type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "proofPurpose": "acceptance",
             "verificationMethod": f"urn:meridian:key:{e.acceptor_kid}", "proofValue": "u" + b64u(e.sig_v)},
        ],
    }


def vc_size(e: Edge) -> int:
    return len(canonical(edge_to_vc(e)))


def edge_to_sdjwt(e: Edge, issuer_key: KeyPair, selectively_disclosable: Tuple[str, ...] = ("scope", "subject")) -> Tuple[str, List[str]]:
    """Issue an SD-JWT VC for the edge. Returns (compact token, disclosures)."""
    p = e.payload()
    claims: Dict = {"iss": e.issuer_kid, "vct": "urn:meridian:receiving-authority", "type": e.etype,
                    "u": e.src, "v": e.dst, "nbf": e.valid_from, "exp": e.valid_until,
                    "status": {"status_list": {"idx": e.status.index, "uri": e.status.list_id}}}
    disclosures: List[str] = []
    sd: List[str] = []
    for name in selectively_disclosable:
        salt = b64u(os.urandom(16))
        disc = b64u(json.dumps([salt, name, p.get(name)], separators=(",", ":")).encode())
        disclosures.append(disc)
        sd.append(b64u(sha256(disc.encode())))
    claims["_sd"] = sorted(sd)
    claims["_sd_alg"] = "sha-256"
    header = {"alg": "EdDSA" if issuer_key.alg == "Ed25519" else "ES256", "typ": "dc+sd-jwt", "kid": issuer_key.kid}
    signing_input = b64u(canonical(header)) + "." + b64u(canonical(claims))
    sig = issuer_key.sign(signing_input.encode())
    token = signing_input + "." + b64u(sig)
    return token + "~" + "~".join(disclosures) + "~", disclosures
