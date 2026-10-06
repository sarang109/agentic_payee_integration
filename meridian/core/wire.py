"""JSON wire encoding for edges and status snapshots (directory and status
services)."""

from __future__ import annotations

import base64
import zlib

from .edges import Edge, StatusRef
from .scope import Scope
from .status import StatusSnapshot


def _b(x: bytes) -> str:
    return base64.b64encode(x).decode()


def _u(s: str) -> bytes:
    return base64.b64decode(s)


def edge_to_json(e: Edge) -> dict:
    return {**e.payload(), "sig_u": _b(e.sig_u), "sig_v": _b(e.sig_v)}


def edge_from_json(d: dict) -> Edge:
    return Edge(d["type"], d["u"], d["v"], Scope.from_json(d["scope"]), d["nbf"], d["exp"],
                StatusRef(d["status"]["list"], d["status"]["idx"]), d["iss"], d["iss_class"], d["acc"],
                d["delegate"], d["kappa"], d["subject"], d["iat"], d["nonce"], _u(d["sig_u"]), _u(d["sig_v"]))


def snapshot_to_json(s: StatusSnapshot) -> dict:
    return {"list": s.list_id, "iat": s.issued_at, "bits": _b(zlib.compress(s.bits)), "iss": s.issuer_kid,
            "sig": _b(s.sig)}


def snapshot_from_json(d: dict) -> StatusSnapshot:
    return StatusSnapshot(d["list"], d["iat"], zlib.decompress(_u(d["bits"])), d["iss"], _u(d["sig"]))
