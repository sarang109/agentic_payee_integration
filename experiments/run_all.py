"""Regenerate every table and figure from fixed seeds.

    python -m experiments.run_all            # full run
    MERIDIAN_QUICK=1 python -m experiments.run_all   # smoke run
    python -m experiments.run_all --only e2,e6

Order matters: E4 calibrates anchoring before E2 uses it. E2-E6 refuse to
run if the pre-registration file changed after it was locked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback

from .common import RESULTS, ROOT, Timer, environment, manifest, write_json

STEPS = ["formal", "toys", "e4", "e4b", "e4c", "e1", "e2", "e5", "e6", "stripe", "x402", "e7", "e8", "e9", "e10", "ablations"]
PREREG_GATED = {"e2", "e5", "e6"}


def prereg_ok() -> tuple[bool, str]:
    with open(os.path.join(ROOT, "preregistration", "hypotheses.yaml"), "rb") as fh:
        h = hashlib.sha256(fh.read()).hexdigest()
    with open(os.path.join(ROOT, "preregistration", "LOCK")) as fh:
        lock = fh.read().strip()
    return h == lock, h


def _run(step: str):
    if step == "formal":
        from .formal_check import run_formal
        return run_formal()
    if step == "toys":
        from .toys import run_toys
        return run_toys()
    if step == "e1":
        from .e1_v1a_v1b import run_e1
        return run_e1()
    if step == "e2":
        from .e2_e3 import run_e2_e3
        return run_e2_e3()
    if step == "e4":
        from .e4_anchoring import run_e4
        return run_e4()
    if step == "e4b":
        from .e4b_phishing import run_e4b
        return run_e4b()
    if step == "e4c":
        from .e4c_kaggle import run_e4c
        return run_e4c()
    if step == "stripe":
        from .stripe_connect import run_connect
        return run_connect()
    if step == "x402":
        from .x402_testnet import run_x402_testnet
        return run_x402_testnet()
    if step == "e5":
        from .e5_probation import run_e5
        return run_e5()
    if step == "e6":
        from .e6_rails import run_e6
        return run_e6()
    if step == "e7":
        from .e7_privacy import run_e7
        return run_e7()
    if step == "e8":
        from .e8_scale import run_e8
        return run_e8()
    if step == "e9":
        from .e9_agents import run_e9
        return run_e9()
    if step == "e10":
        from .e10_coverage import run_e10
        return run_e10()
    if step == "ablations":
        from .ablations import run_ablations
        return run_ablations()
    raise ValueError(step)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated subset of " + ",".join(STEPS))
    ap.add_argument("--skip", default="", help="comma-separated steps to skip (e.g. e10 when offline)")
    args = ap.parse_args()
    steps = [s for s in STEPS if (not args.only or s in args.only.split(",")) and s not in args.skip.split(",")]
    ok, h = prereg_ok()
    status = {"environment": environment(), "preregistration_sha256": h, "preregistration_locked": ok, "steps": {}}
    prev_path = os.path.join(RESULTS, "run_status.json")
    if args.only and os.path.exists(prev_path):
        # a partial rerun keeps the record of the steps it did not touch
        with open(prev_path) as fh:
            status["steps"] = json.load(fh).get("steps", {})
    t_all = time.perf_counter()
    for step in steps:
        if step in PREREG_GATED and not ok:
            status["steps"][step] = {"status": "refused: pre-registration changed after lock"}
            print(f"!! {step} refused: preregistration/hypotheses.yaml does not match preregistration/LOCK")
            continue
        t0 = time.perf_counter()
        try:
            with Timer(f"step {step}"):
                summary = _run(step)
            st = summary.get("status", "ok") if isinstance(summary, dict) else "ok"
            status["steps"][step] = {"status": st if str(st).startswith("skipped") else "ok",
                                     "seconds": round(time.perf_counter() - t0, 1)}
        except Exception as e:  # keep going; record the failure in the status file
            traceback.print_exc()
            status["steps"][step] = {"status": f"failed: {type(e).__name__}: {e}"[:500],
                                     "seconds": round(time.perf_counter() - t0, 1)}
    from .figures import make_all
    make_all()
    status["total_seconds"] = round(time.perf_counter() - t_all, 1)
    write_json("run_status", status, folder=RESULTS)
    from .report import build_report
    build_report()
    manifest()
    failed = [s for s, v in status["steps"].items() if v["status"] != "ok"]
    print("failed steps:", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
