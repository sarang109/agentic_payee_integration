"""E7 privacy cost (V4) and H4 decision agreement.

* Groth16 membership proofs (circom + snarkjs, Poseidon Merkle tree, depth 16)
  and BBS selective-disclosure presentations (IETF draft, BLS12-381-SHA-256):
  generation and verification time, proof size.
* Private log lookups: k-anonymous hash prefixes and two-server XOR PIR.
* H4: M4 (V4 pre-check) against M3 on the same chronological bench, case by
  case, with the extra payer-side latency.
* Identifiers revealed per payment for each variant.
"""

from __future__ import annotations

import os
import random
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from meridian.core import grammar
from meridian.core.decision import ALLOW, DENY, STEP_UP
from meridian.core.ids import L0, layer
from meridian.core.pav import verify_binding
from meridian.core.policy import Policy, allowed
from meridian.core.routes import PAYOUT
from meridian.core.scope import PaymentTuple, Scope
from meridian.log import HIGH, edge_risk
from meridian.zk import available, shared
from meridian.zk.bbs_edges import BBSEdges, new_salt
from meridian.zk.lookup import KAnonLookup, XorPIR
from meridian.zk.membership import MembershipLog, RouteSummary
from payeebench.configs import anchor
from payeebench.runner import build_bench, run

from .common import QUICK, SEED, Timer, write_csv, write_json, write_table
from .e2_e3 import calibrated_cba
from .stats import fmt_rate


# ------------------------------------------------------------------ admission

class Admission:
    """The log's admission engine for V4: decides, at time t, which route
    summaries are in a brand's committed set. It checks the standing route
    (signatures, issuer classes, grammar with terminal continuity, revocation
    status now, MTL inclusion, objections, probation) but not the payment."""

    def __init__(self, world, ctx, mlog: MembershipLog) -> None:
        self.w, self.ctx, self.mlog = world, ctx, mlog

    def summary(self, bundle, t: int) -> Optional[RouteSummary]:
        s, _ = self.summary_with_reason(bundle, t)
        return s

    def summary_with_reason(self, bundle, t: int):
        w = self.w
        chain = list(bundle.rap.edges) + list(bundle.onward)
        term_edge = bundle.terminal
        edges = chain + ([term_edge] if term_edge is not None else [])
        if not chain or layer(chain[0].src) != L0:
            return None, "no-brand-root"
        if any(chain[i - 1].dst != e.src for i, e in enumerate(chain) if i):
            return None, "chain-break"
        pol = Policy(rho=0, grammar=False, use_scope_meet=False)
        sc = None
        for e in edges:
            ok, why = allowed(e, w.trust, pol)
            if not ok:
                return None, why
            if not e.valid_at(t):
                return None, "expired"
            if w.sr.lists[e.status.list_id].snapshot(t).revoked(e.status.index):
                return None, "revoked"
            sc = e.scope if sc is None else sc.meet(e.scope)
        g = grammar.run(edges, require_terminal=True)
        if not g.ok:
            positive = "subject" in g.reason or "different principal" in g.reason
            return None, "subject-mismatch" if positive else "grammar"
        # MTL: every edge logged without objection; probation pushes not_before
        lv = self.ctx.log_verifier
        not_before = 0
        for e in edges:
            r = lv.accept_edge(e, t)
            if not r.ok and r.reason != "probation":
                return None, "mtl-" + r.reason
            entry = w.log.lookup(e.eid)
            if entry is not None and edge_risk(e) == HIGH:
                not_before = max(not_before, entry.t_log + lv.delta)
        for c in bundle.commitments:
            if c.kind == PAYOUT:
                key = f"payout:{c.custodian}->{c.next_hop}"
                r = lv.accept_key(key, HIGH, t)
                if not r.ok and r.reason != "probation":
                    return None, "mtl-" + r.reason
                entry = w.log.lookup(key)
                if entry is not None:
                    not_before = max(not_before, entry.t_log + lv.delta)
        terminal = bundle.committed_terminal()
        if terminal is None:
            return None, "no-commitment"
        not_after = min(e.valid_until for e in edges)
        return RouteSummary(chain[0].src, bundle.rap.edges[-1].dst, terminal, sc, not_before, not_after,
                            blinding=int.from_bytes(os.urandom(16), "big")), ""


def m4_decide(case, ctx, adm: Admission, mlog: MembershipLog) -> Dict:
    t0 = time.perf_counter()
    a = anchor(case, ctx)
    if not a.committed:
        return {"m4": STEP_UP, "m4_stage": "cba", "m4_verify_ms": 0.0, "m4_prove_ms": 0.0}
    b = a.brand
    t = case.payment.t
    bundle = case.bundle
    if bundle is None or not bundle.rap.edges:
        return {"m4": STEP_UP, "m4_stage": "no-proof", "m4_verify_ms": 0.0, "m4_prove_ms": 0.0}
    s, why = adm.summary_with_reason(bundle, t)
    mlog.sets = {}
    mlog._trees = {}
    if s is not None:
        mlog.admit(s)
    # positive evidence of mismatch denies, missing evidence steps up (as M3)
    positive = {"subject-mismatch", "mtl-objection", "sig-authorize", "sig-accept", "chain-break"}
    if s is None:
        return {"m4": DENY if why in positive else STEP_UP, "m4_stage": "admission:" + why,
                "m4_verify_ms": 0.0, "m4_prove_ms": 0.0}
    if s.brand != b:
        return {"m4": DENY, "m4_stage": "membership-other-brand", "m4_verify_ms": 0.0, "m4_prove_ms": 0.0}
    # per-payment parts: binding token, and the operator's commitment chain
    ok, why = verify_binding(bundle.rap.binding, case.payment, bundle.rap.edges[-1], ctx.world.trust)
    if not ok:
        return {"m4": DENY if why in ("beta-sig", "beta-mismatch") else STEP_UP, "m4_stage": "beta",
                "m4_verify_ms": 0.0, "m4_prove_ms": 0.0}
    custodians = bundle.custodians()
    by_h = {c.custodian: c for c in bundle.commitments}
    for h in custodians:
        c = by_h.get(h)
        if c is None:
            return {"m4": STEP_UP, "m4_stage": "commitment", "m4_verify_ms": 0.0, "m4_prove_ms": 0.0}
        if c.signer_kid != bundle.acceptor_of(h) or not c.verify(ctx.world.trust) \
                or c.beta_digest != bundle.rap.binding.digest or c.payment_id != case.payment.payment_id:
            return {"m4": DENY, "m4_stage": "commitment", "m4_verify_ms": 0.0, "m4_prove_ms": 0.0}
    prover_t0 = time.perf_counter()
    res = mlog.prove(b, case.payment.payee, case.payment.tuple, t)
    prove_ms = (time.perf_counter() - prover_t0) * 1000
    if res is None:
        # no admitted leaf covers this payment: probation, scope or validity
        return {"m4": STEP_UP, "m4_stage": "no-witness", "m4_verify_ms": 0.0, "m4_prove_ms": prove_ms}
    proof, tc = res
    v0 = time.perf_counter()
    ok, vms = mlog.verify(b, case.payment.payee, case.payment.tuple, t, proof, tc)
    verify_wall = (time.perf_counter() - v0) * 1000
    return {"m4": ALLOW if ok else DENY, "m4_stage": "snark", "m4_verify_ms": verify_wall,
            "m4_prove_ms": proof.prove_ms, "m4_proof_json_bytes": proof.bytes,
            "m4_total_ms": (time.perf_counter() - t0) * 1000}


# ------------------------------------------------------------------ main

def run_e7() -> dict:
    if not available():
        raise RuntimeError("zk toolchain missing; run zk/setup.sh")
    w = shared()
    out: Dict = {}

    # (a) SNARK micro-benchmarks
    mlog = MembershipLog(w)
    n = 5 if QUICK else 30
    rows = []
    with Timer(f"E7 {n} Groth16 membership proofs"):
        for i in range(n):
            mlog.sets, mlog._trees = {}, {}
            for j in range(1 + i % 8):
                mlog.admit(RouteSummary(f"brand:b{i}.com", f"proc:psp/acct_{j}", f"acct:bank/{j}",
                                        Scope.make(rails={"card"}, currencies={"USD"}, ceiling=100_000), 0, 10**9))
            tup = PaymentTuple("card", "USD", 5000 + i, "5661", "US")
            proof, tc = mlog.prove(f"brand:b{i}.com", "proc:psp/acct_0", tup, 1000)
            ok, vms = mlog.verify(f"brand:b{i}.com", "proc:psp/acct_0", tup, 1000, proof, tc)
            rows.append({"prove_ms": proof.prove_ms, "verify_ms": vms, "proof_json_bytes": proof.bytes, "ok": ok})
    sn = pd.DataFrame(rows)
    write_csv("e7_snark", sn)

    # (b) BBS presentations for k edges
    bb = BBSEdges(w)
    world, _ = build_bench(seed=SEED + 3, n_attack=0, n_benign=3, n_pv=0, attacks=[], pvs=[])
    brows = []
    with Timer("E7 BBS presentations"):
        tpls = [t for br in world.brands.values() for t in br.templates if t.rap_edges]
        for k in (2, 3, 4):
            # chained receiving-authority edges only (the terminal binding is
            # checked separately), so k is at most the longest real chain
            cand = [t for t in tpls if len(t.rap_edges) + len(t.onward) == k]
            for rep in range(2 if QUICK else 6):
                tpl = cand[rep % len(cand)]
                edges = list(tpl.rap_edges) + list(tpl.onward)
                salts = {nname: new_salt() for e in edges for nname in (e.src, e.dst)}
                creds = [bb.issue(e, salts) for e in edges]
                nonce = os.urandom(16)
                pres = bb.present(creds, nonce)
                trusted = {c.issuer_pk for c in creds}
                pay = world.make_payment(tpl, tpl.rails[0], 1000, edges[0].valid_from + 1000, random.Random(rep))
                ok, vms, why = bb.verify(pres, edges[0].src, edges[-1].dst, pay.tuple, pay.t, nonce, trusted)
                brows.append({"k_edges": len(edges), "derive_ms": pres.derive_ms, "verify_ms": vms,
                              "bytes": pres.bytes, "ok": ok, "why": why})
    bdf = pd.DataFrame(brows)
    write_csv("e7_bbs", bdf)

    # (c) private lookups
    lrows = []
    N = 50_000 if QUICK else 200_000
    keys = {f"brand:{i}.example": os.urandom(8) for i in range(N)}
    for bits in (8, 12, 16, 20):
        kl = KAnonLookup(keys, bits)
        probes = random.Random(SEED).sample(list(keys), 200)
        sizes, resp = [], []
        for k in probes:
            v, anon, b = kl.query(k)
            sizes.append(anon)
            resp.append(b)
        lrows.append({"scheme": f"k-anon prefix {bits} bits", "records": N, "median anonymity set": int(np.median(sizes)),
                      "response bytes (median)": int(np.median(resp)), "upload bytes": (bits + 7) // 8})
    prng = np.random.default_rng(SEED)
    for logn in (12, 14, 16):
        recs = [os.urandom(64) for _ in range(2 ** logn)]
        pir = XorPIR.from_records(recs, 64)
        t0 = time.perf_counter()
        got, comm = pir.query(123, prng)
        ms = (time.perf_counter() - t0) * 1000
        assert got == recs[123]
        lrows.append({"scheme": f"2-server XOR PIR, 2^{logn} records", "records": 2 ** logn,
                      "median anonymity set": 2 ** logn, "response bytes (median)": 128, "upload bytes": comm - 128,
                      "server+client ms": round(ms, 2)})
    write_table("e7_lookups", pd.DataFrame(lrows), "E7: private log lookups", index=False)

    # (d) H4 on the chronological bench
    world, cases = build_bench(seed=SEED + 5, n_attack=4 if QUICK else 12, n_benign=4 if QUICK else 10, n_pv=0,
                               attacks=["A1", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A11", "A12"], pvs=[])
    mlog4 = MembershipLog(w)
    holder = {}

    def hook(case, ctx, outs):
        if "adm" not in holder:
            holder["adm"] = Admission(world, ctx, mlog4)
        return m4_decide(case, ctx, holder["adm"], mlog4)

    with Timer(f"E7 H4 agreement on {len(cases)} chronological cases (M3 vs M4)"):
        recs = run(world, cases, ["M3"], seed=SEED, hook=hook, cba_params=calibrated_cba())
    df = pd.DataFrame(recs)
    # compare pre-authorization verdicts: M3 verdict without the RWS step-up
    df["m3_pre"] = df.apply(lambda r: ALLOW if r.stage == "rws" else r.verdict, axis=1)
    agree = df.m3_pre == df.m4
    blockagree = (df.m3_pre == ALLOW) == (df.m4 == ALLOW)
    write_csv("e7_h4_cases", df)
    dis = df[~agree].groupby(["kind", "variant", "m3_pre", "m4", "stage", "m4_stage"]).size().reset_index(name="n")
    write_table("e7_h4_disagreements", dis, "E7/H4: cases where the V4 pre-check decides differently from M3",
                index=False)
    allowed = df[df.m4 == ALLOW]
    m3_ms = df[df.m3_pre == ALLOW].decision_ms
    lat = pd.DataFrame([
        {"quantity": "Groth16 prove (prover side)", "p50_ms": sn.prove_ms.median(), "p95_ms": sn.prove_ms.quantile(0.95)},
        {"quantity": "Groth16 verify (payer side)", "p50_ms": sn.verify_ms.median(), "p95_ms": sn.verify_ms.quantile(0.95)},
        {"quantity": "V4 payer-side verify in bench (wall)", "p50_ms": allowed.m4_verify_ms.median(),
         "p95_ms": allowed.m4_verify_ms.quantile(0.95)},
        {"quantity": "M3 pre-check (V1+V2) in bench", "p50_ms": m3_ms.median(), "p95_ms": m3_ms.quantile(0.95)},
        {"quantity": "BBS derive, k=3 (prover side)", "p50_ms": bdf[bdf.k_edges == 3].derive_ms.median(),
         "p95_ms": bdf[bdf.k_edges == 3].derive_ms.quantile(0.95)},
        {"quantity": "BBS verify, k=3 (payer side)", "p50_ms": bdf[bdf.k_edges == 3].verify_ms.median(),
         "p95_ms": bdf[bdf.k_edges == 3].verify_ms.quantile(0.95)},
    ]).round(2)
    write_table("e7_latency", lat, "E7: proof cost (ms)", index=False)
    sizes = pd.DataFrame([
        {"artifact": "Groth16 proof (snarkjs JSON)", "bytes": int(sn.proof_json_bytes.median())},
        {"artifact": "Groth16 proof (2 G1 + 1 G2, compressed)", "bytes": 128},
        *[{"artifact": f"BBS presentation, k={k}", "bytes": int(g.bytes.median())} for k, g in bdf.groupby("k_edges")],
    ])
    write_table("e7_sizes", sizes, "E7: proof size", index=False)

    a16 = next(r["median anonymity set"] for r in lrows if r["scheme"] == "k-anon prefix 16 bits")
    a12 = next(r["median anonymity set"] for r in lrows if r["scheme"] == "k-anon prefix 12 bits")
    leak = pd.DataFrame([
        {"variant": "V1b / M1", "payer learns": "full path: brand, entity, platform, PSP account, payout account "
         "(hashed), every issuer", "hidden from payer": "nothing", "third parties learn": "-",
         "linkable across payments": "yes (path identifiers)"},
        {"variant": "V1a", "payer learns": "as V1b", "hidden from payer": "nothing",
         "third parties learn": "directory: brand, payee, amount, time", "linkable across payments": "yes"},
        {"variant": "V2 log lookup (plain)", "payer learns": "-", "hidden from payer": "-",
         "third parties learn": "log operator: every edge id queried", "linkable across payments": "yes (by the log)"},
        {"variant": "V2 log lookup (k-anon, 16-bit prefix)", "payer learns": "-", "hidden from payer": "-",
         "third parties learn": f"log operator: a prefix shared by ~{a16} records (~{a12} at 12 bits)",
         "linkable across payments": "partly (prefix repeats)"},
        {"variant": "V2 log lookup (2-server PIR)", "payer learns": "-", "hidden from payer": "-",
         "third parties learn": "nothing, unless the two servers collude", "linkable across payments": "no"},
        {"variant": "V3 observers", "payer learns": "first hop, transfer records, terminal credit",
         "hidden from payer": "-", "third parties learn": "observers: the payment id",
         "linkable across payments": "yes (by observers)"},
        {"variant": "V4 SNARK", "payer learns": "brand, payee p, hiding commitment to terminal, ALLOW bit",
         "hidden from payer": "intermediate entities, platform, PSP and payout accounts, issuers, scopes, terminal "
         "account", "third parties learn": "-", "linkable across payments": "yes, per merchant (same p and commitment)"},
        {"variant": "V4 BBS", "payer learns": "brand, payee p, edge types, scopes, salted link tags, issuer keys",
         "hidden from payer": "intermediate entity identities and accounts", "third parties learn": "-",
         "linkable across payments": "yes, per merchant (link tags, issuer keys)"},
    ])
    write_table("e7_leakage", leak, "E7: what each variant reveals per payment",
                "T9 is scoped to the 'hidden from payer' column: V4 hides the acquiring relationships and the "
                "terminal account. It does not hide the brand or the payee identifier the payment is addressed to, "
                "and proofs for the same merchant are linkable. Anonymity sets are for a log of "
                f"{lrows[0]['records']:,} records and shrink as the log grows.", index=False)

    out["H4"] = {
        "cases": len(df), "exact_verdict_agreement": fmt_rate(int(agree.sum()), len(df)),
        "allow_block_agreement": fmt_rate(int(blockagree.sum()), len(df)),
        "added_payer_p95_ms": float(allowed.m4_verify_ms.quantile(0.95)) if len(allowed) else None,
        "prover_p95_ms": float(sn.prove_ms.quantile(0.95)),
        "variant": "SNARK (Groth16); decision agreement and latency are measured for this variant",
        "bbs_verify_p95_ms": float(bdf[bdf.k_edges == 3].verify_ms.quantile(0.95)),
        "bbs_meets_latency_target": bool(bdf[bdf.k_edges == 3].verify_ms.quantile(0.95) <= 150),
        "supported": bool(agree.all() and len(allowed) and allowed.m4_verify_ms.quantile(0.95) <= 150),
    }
    out["snark"] = {"prove_p50_ms": float(sn.prove_ms.median()), "verify_p50_ms": float(sn.verify_ms.median()),
                    "all_verified": bool(sn.ok.all())}
    out["bbs_all_verified"] = bool(bdf.ok.all())
    write_json("e7_summary", out)
    return out


if __name__ == "__main__":
    print(run_e7())
