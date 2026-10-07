"""Pre-registration locks.

    python -m experiments.prereg status      # show both locks
    python -m experiments.prereg lock-v2     # write preregistration/LOCK_V2

The v1 file (H1-H5) is locked in ``preregistration/LOCK``. The v2 file (H6) has
its own lock and records the SHA-256 of the v1 file. ``lock-v2`` refuses to
overwrite an existing lock: a changed file means a new registration, not an
edit.
"""

from __future__ import annotations

import hashlib
import os
import sys
from typing import Dict, Tuple

import yaml

from .common import ROOT

PREREG = os.path.join(ROOT, "preregistration")
V1 = os.path.join(PREREG, "hypotheses.yaml")
V1_LOCK = os.path.join(PREREG, "LOCK")
V2 = os.path.join(PREREG, "hypotheses_v2.yaml")
V2_LOCK = os.path.join(PREREG, "LOCK_V2")


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _read_lock(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return fh.read().strip()


def v1_ok() -> Tuple[bool, str]:
    h = sha256_file(V1)
    return h == _read_lock(V1_LOCK), h


def v2_status() -> Dict[str, object]:
    """State of the second registration. ``ok`` is true only if the v1 lock
    holds, the v2 file records the v1 hash, and the v2 file matches its lock."""
    out: Dict[str, object] = {"v1_ok": False, "v2_present": os.path.exists(V2), "v2_locked": False,
                              "v2_sha256": None, "ok": False, "reason": ""}
    out["v1_ok"] = v1_ok()[0]
    if not out["v2_present"]:
        out["reason"] = "preregistration/hypotheses_v2.yaml is missing"
        return out
    out["v2_sha256"] = sha256_file(V2)
    lock = _read_lock(V2_LOCK)
    if lock is None:
        out["reason"] = "preregistration/LOCK_V2 does not exist: lock hypotheses_v2.yaml before running E11"
        return out
    out["v2_locked"] = True
    with open(V2) as fh:
        recorded = (yaml.safe_load(fh) or {}).get("v1_sha256")
    if not out["v1_ok"]:
        out["reason"] = "preregistration/hypotheses.yaml does not match preregistration/LOCK"
    elif recorded != sha256_file(V1):
        out["reason"] = "v1_sha256 in hypotheses_v2.yaml does not match preregistration/hypotheses.yaml"
    elif out["v2_sha256"] != lock:
        out["reason"] = "hypotheses_v2.yaml changed after it was locked"
    else:
        out["ok"] = True
    return out


def load_v2() -> dict:
    with open(V2) as fh:
        return yaml.safe_load(fh)


def lock_v2() -> int:
    if os.path.exists(V2_LOCK):
        print("preregistration/LOCK_V2 already exists; a changed registration needs a new file, not an edit.")
        return 1
    if not v1_ok()[0]:
        print("preregistration/hypotheses.yaml does not match preregistration/LOCK; refusing to lock v2.")
        return 1
    with open(V2) as fh:
        if (yaml.safe_load(fh) or {}).get("v1_sha256") != sha256_file(V1):
            print("v1_sha256 in hypotheses_v2.yaml does not match preregistration/hypotheses.yaml.")
            return 1
    h = sha256_file(V2)
    with open(V2_LOCK, "w") as fh:
        fh.write(h + "\n")
    print(f"locked hypotheses_v2.yaml: {h}")
    return 0


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "lock-v2":
        return lock_v2()
    if cmd == "status":
        print("v1:", "locked, unchanged" if v1_ok()[0] else "MISMATCH")
        s = v2_status()
        print("v2:", "locked, unchanged" if s["ok"] else f"not usable: {s['reason']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
