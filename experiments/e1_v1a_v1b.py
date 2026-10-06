"""E1 foundational comparison: V1a directory lookup vs V1b proof-carrying RAP.

Measures decision equivalence on identical inputs, added latency (p50/p95)
over real localhost HTTP services, behaviour under directory outage and
under a lying directory, and information revealed per payment. A modelled
wide-area round trip is reported separately and labelled as such.
"""

from __future__ import annotations

import json
import random
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List

import numpy as np
import pandas as pd

from meridian.core.decision import ALLOW, DENY, STEP_UP
from meridian.core.directory import Directory, v1a_verify
from meridian.core.pav import RAP, check_edges, pav, verify_binding
from meridian.core.decision import Decision
from meridian.core.policy import Policy
from meridian.core.scope import PaymentTuple
from meridian.core.wire import edge_from_json, edge_to_json, snapshot_from_json, snapshot_to_json
from payeebench.runner import build_bench

from .common import QUICK, SEED, Timer, write_csv, write_json, write_table
from .stats import fmt_rate


def all_edges(world):
    issuers = [world.dv, world.dv_careless, world.qvi, *world.operators().values(), *world.entity_issuers.values()]
    seen, out = set(), []
    for i in issuers:
        for e in i.issued:
            if e.eid not in seen:
                seen.add(e.eid)
                out.append(e)
    return out


class _Services:
    """Directory and status-list HTTP services on localhost."""

    def __init__(self, directory: Directory, world) -> None:
        self.directory = directory
        self.world = world
        d, w = directory, world

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                t = PaymentTuple(**body["tuple"])
                ans = d.query(body["anchor"], body["payee"], t, body["t"], body["d_max"], body["rho"])
                out = {"reachable": ans["reachable"], "others": ans["others"],
                       "edges": [edge_to_json(e) for e in ans["edges"]],
                       "status": {k: snapshot_to_json(s) for k, s in ans["status"].items()}}
                data = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                _, _, list_id, t = self.path.split("/", 3)
                snap = w.sr.lists[list_id].snapshot(int(t))
                data = json.dumps(snapshot_to_json(snap)).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def query(self, anchor, payment, policy) -> dict:
        req = {"anchor": anchor, "payee": payment.payee, "tuple": payment.tuple.__dict__, "t": payment.t,
               "d_max": policy.d_max, "rho": policy.rho}
        r = urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:{self.port}/query", json.dumps(req).encode(), {"Content-Type": "application/json"}),
            timeout=10)
        ans = json.loads(r.read())
        return {"reachable": ans["reachable"], "others": ans["others"],
                "edges": [edge_from_json(e) for e in ans["edges"]],
                "status": {k: snapshot_from_json(s) for k, s in ans["status"].items()}}

    def status(self, list_id: str, t: int):
        r = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/status/{list_id}/{t}", timeout=10)
        return snapshot_from_json(json.loads(r.read()))

    def close(self):
        self.httpd.shutdown()


def v1a_http(svc: _Services, payment, anchor, beta, policy, trust) -> Decision:
    """V1a over HTTP: identical decision logic to v1a_verify, network included."""
    ans = svc.query(anchor, payment, policy)
    if not ans["reachable"] or not ans["edges"]:
        if ans["others"]:
            return Decision(DENY, reasons=["path-to-different-entity"], stage="v1a")
        return Decision(STEP_UP, reasons=["no-path"], stage="v1a")
    pc = check_edges(ans["edges"], ans["status"], payment.tuple, payment.t, policy, trust)
    if not pc.ok:
        return Decision(DENY if pc.tamper and policy.deny_on_tamper else STEP_UP, reasons=pc.reasons, stage="v1a")
    ok, why = verify_binding(beta, payment, ans["edges"][-1], trust)
    if not ok:
        return Decision(DENY if why in ("beta-sig", "beta-mismatch") else STEP_UP, reasons=[why], stage="v1a")
    return Decision(ALLOW, 1, [], anchor, stage="v1a")


def run_e1() -> dict:
    n_attack, n_benign = (8, 10) if QUICK else (30, 40)
    with Timer("E1 build"):
        world, cases = build_bench(seed=SEED + 1, n_attack=n_attack, n_benign=n_benign, n_pv=0,
                                   attacks=["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A11"])
    policy = Policy(grammar=True, rho=300)
    directory = Directory(world.sr)
    directory.add_all(all_edges(world))
    svc = _Services(directory, world)
    rng = np.random.default_rng(SEED)
    rows: List[Dict] = []
    try:
        with Timer(f"E1 decisions and latency on {len(cases)} cases"):
            for c in cases:
                anchor = c.listing.brand_claim
                beta = c.bundle.rap.binding if c.bundle else None
                rap = c.bundle.rap if c.bundle else None
                t0 = time.perf_counter()
                d_b = pav(rap, c.payment, anchor, policy, world.trust)
                lat_b = (time.perf_counter() - t0) * 1000
                # V1b with synchronous status: the verifier fetches each list itself
                t0 = time.perf_counter()
                if rap is not None:
                    fresh = {lid: svc.status(lid, c.payment.t) for lid in rap.status}
                    d_bs = pav(RAP(rap.edges, fresh, rap.binding), c.payment, anchor, policy, world.trust)
                else:
                    d_bs = d_b
                lat_bs = (time.perf_counter() - t0) * 1000
                t0 = time.perf_counter()
                d_a = v1a_http(svc, c.payment, anchor, beta, policy, world.trust)
                lat_a = (time.perf_counter() - t0) * 1000
                rows.append({"case_id": c.case_id, "kind": c.kind, "v1b": d_b.verdict, "v1b_sync": d_bs.verdict,
                             "v1a": d_a.verdict, "v1b_ms": lat_b, "v1b_sync_ms": lat_bs, "v1a_ms": lat_a,
                             "v1b_reason": ";".join(d_b.reasons[:2]), "v1a_reason": ";".join(d_a.reasons[:2]),
                             "status_lists": len(rap.status) if rap else 0})
    finally:
        svc.close()
    df = pd.DataFrame(rows)
    write_csv("e1_decisions", df)

    agree = (df.v1a == df.v1b)
    dis = df[~agree].groupby(["kind", "v1b", "v1a", "v1b_reason", "v1a_reason"]).size().reset_index(name="n")
    write_table("e1_disagreements", dis, "E1: cases where V1a and V1b decide differently", index=False)

    rtt = 40.0 * np.exp(rng.normal(0, 0.5, len(df)))  # modelled WAN round trip (ms)
    lat = pd.DataFrame([
        {"variant": "V1b (stapled status)", "p50_ms": df.v1b_ms.median(), "p95_ms": df.v1b_ms.quantile(0.95),
         "p95_with_modelled_wan_ms": df.v1b_ms.quantile(0.95), "third_party_round_trips": 0},
        {"variant": "V1b + synchronous status fetch", "p50_ms": df.v1b_sync_ms.median(),
         "p95_ms": df.v1b_sync_ms.quantile(0.95),
         "p95_with_modelled_wan_ms": np.quantile(df.v1b_sync_ms + rtt, 0.95), "third_party_round_trips": 1},
        {"variant": "V1a directory (signed answers)", "p50_ms": df.v1a_ms.median(), "p95_ms": df.v1a_ms.quantile(0.95),
         "p95_with_modelled_wan_ms": np.quantile(df.v1a_ms + rtt, 0.95), "third_party_round_trips": 1},
    ])
    write_table("e1_latency", lat.round(3), "E1: added verifier latency (localhost HTTP; WAN column adds a modelled "
                "lognormal RTT, median 40 ms)", index=False)

    # outage and lying directory -----------------------------------------------
    life = []
    sample = cases
    for mode in ["outage", "omit", "stale", "forge", "assert"]:
        for trusting in (False, True):
            directory.lying = None if mode == "outage" else mode
            directory.lie_targets = {c.payment.payee for c in sample}
            n_ben_ok = n_ben = n_att_loss = n_att = 0
            for c in sample:
                beta = c.bundle.rap.binding if c.bundle else None
                d = v1a_verify(directory, c.payment, c.listing.brand_claim, beta, policy, world.trust,
                               trusting=trusting, available=(mode != "outage"))
                legit = c.exec_terminal in world.legit_terminals(c.intended, c.payment.tuple)
                if c.is_attack:
                    n_att += 1
                    n_att_loss += int(d.verdict == ALLOW and not legit)
                else:
                    n_ben += 1
                    n_ben_ok += int(d.verdict == ALLOW)
            life.append({"directory": mode, "client": "trusting" if trusting else "checks signatures",
                         "benign allowed": f"{n_ben_ok}/{n_ben}", "attack losses": f"{n_att_loss}/{n_att}"})
    directory.lying = None
    vb_ben = df[df.kind == "benign"]
    life.append({"directory": "(V1b, no directory)", "client": "-",
                 "benign allowed": f"{int((vb_ben.v1b == ALLOW).sum())}/{len(vb_ben)}",
                 "attack losses": "see E2 (M1-G1)"})
    write_table("e1_outage_lying", pd.DataFrame(life), "E1: V1a under outage and a lying directory (all payees "
                "targeted)", index=False)

    leak = pd.DataFrame([
        {"variant": "V1a", "third party": "directory", "learns per payment": "anchor brand, payee, amount, rail, time",
         "identifiers": 5, "anonymity set": 1},
        {"variant": "V1b stapled", "third party": "none", "learns per payment": "-", "identifiers": 0,
         "anonymity set": "-"},
        {"variant": "V1b synchronous status", "third party": "status-list host",
         "learns per payment": "which status lists were fetched", "identifiers": float(df.status_lists.mean()),
         "anonymity set": "list capacity (65,536 entries)"},
    ])
    write_table("e1_leakage", leak, "E1: information revealed to third parties per payment", index=False)
    block = lambda v: v != ALLOW  # noqa: E731
    agree_allow = (df.v1a.map(block) == df.v1b.map(block))
    summary = {"agreement_exact_verdict": fmt_rate(int(agree.sum()), len(df)),
               "agreement_allow_vs_block": fmt_rate(int(agree_allow.sum()), len(df)), "n": len(df),
               "latency": lat.round(3).to_dict(orient="records")}
    write_json("e1_summary", summary)
    return summary


if __name__ == "__main__":
    print(run_e1())
