"""Hand-built checks from the foundational section.

F3  toy table: B7 combined vs V1 original vs v2 core on S1-S7 and X1-X6,
    compared cell by cell with the blueprint's table
T4  mutation tests on AP2 v0.2 mandates and ACP checkout sessions
F5  split payments: linear verification vs exact search (bin packing)
"""

from __future__ import annotations

import random
import time
from dataclasses import replace
from typing import Dict, List

import numpy as np
import pandas as pd

from meridian.core.decision import ALLOW, DENY, STEP_UP
from meridian.core.discharge import TransferRecord, find_breach, verify_certificate
from meridian.core.edges import AG, SUB
from meridian.core.pav import RAP, BindingToken, pav
from meridian.core.policy import Policy
from meridian.core.routes import PAYOUT, REMIT, Commitment, RouteBundle, verify_route
from meridian.core.scope import Scope
from meridian.core.split import SplitLeg, find_split, verify_split
from meridian.protocols import acp, ap2
from payeebench.cases import AttackerKit, Listing, gen_A6, gen_A8, gen_A13, genuine_listing
from payeebench.configs import Ctx, b7
from payeebench.world import EDGE_LIFETIME, T_EXP_START, World

from .common import SEED, Timer, write_csv, write_json, write_table

BLUEPRINT_F3 = {
    "S1": ("ok", "ok", "ok"), "S2": ("ok", "ok", "ok"), "S3": ("ok", "ok", "ok"), "S4": ("ok", "ok", "ok"),
    "S5": ("ok", "ok", "ok"), "S6": ("false block", "ok", "ok"), "S7": ("ok", "ok", "ok"),
    "X1": ("loss", "stopped", "stopped"), "X2": ("loss", "loss", "stopped"), "X3": ("loss", "loss", "stopped"),
    "X4": ("stopped", "stopped", "stopped"), "X5": ("loss", "loss", "loss, attributable"),
    "X6": ("allow", "allow", "step-up (G1 only)"),
}


def _label(kind: str, verdict: str, lands_legit: bool, attributable: bool = False, level: int = -1,
           benign_no_div: bool = False) -> str:
    if kind == "S":
        return "ok" if verdict == ALLOW else "false block"
    if benign_no_div:
        if verdict == ALLOW:
            return "allow"
        return "step-up (G1 only)" if verdict == STEP_UP and level == 1 else verdict.lower()
    if verdict == ALLOW and not lands_legit:
        return "loss, attributable" if attributable else "loss"
    if verdict == ALLOW:
        return "ok"
    return "stopped"


def f3_toy() -> pd.DataFrame:
    world = World(seed=SEED + 11).build()
    rng = random.Random(SEED + 11)
    kit = AttackerKit(world, rng)
    ctx = Ctx(world, None, Policy(), None, {})
    pol_v1 = Policy(grammar=False)
    pol_v2 = Policy()
    rows = []

    def evaluate(name, case, bundle_meridian=None, b7_case=None, benign_no_div=False):
        bm = bundle_meridian if bundle_meridian is not None else case.bundle
        anchor = case.intended  # V1 and the v2 core are given the correct brand
        d1 = pav(bm.rap if bm else None, case.payment, anchor, pol_v1, world.trust)
        d2 = verify_route(bm, case.payment, anchor, pol_v2, world.trust)
        ob = b7(b7_case or case, ctx)
        legit = case.exec_terminal in world.legit_terminals(case.intended, case.payment.tuple)
        attributable = False
        if d2.verdict == ALLOW and not legit and bm is not None:
            recs = [TransferRecord.issue(k, case.payment.payment_id, s, d, case.payment.amount, case.payment.t + 99)
                    for (s, d, k) in case.exec_hops if k is not None]
            cert = find_breach(bm, recs, world.trust)
            attributable = cert is not None and verify_certificate(cert, world.trust)
        kind = "S" if name.startswith("S") else "X"
        got = (_label(kind, ob.verdict, legit, False, -1, benign_no_div),
               _label(kind, d1.verdict, legit, False, d1.level, benign_no_div),
               _label(kind, d2.verdict, legit, attributable, d2.level, benign_no_div))
        bp = BLUEPRINT_F3[name.split()[0]]
        rows.append({"case": name, "B7 combined": got[0], "V1 original": got[1], "v2 core": got[2],
                     "blueprint (B7 / V1 / v2)": " / ".join(bp), "matches blueprint": got == bp,
                     "v2 reasons": ";".join(d2.reasons[:2])})

    from payeebench.cases import gen_benign
    benign = gen_benign(world, rng, 3)
    pick = {}
    for c in benign:
        s = c.variant
        if s in ("S1", "S2", "S3", "S4", "S5", "S6", "S7") and s not in pick and c.payment.t >= T_EXP_START:
            pick[s] = c
    for s in ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]:
        evaluate(s, pick[s])

    # S6 paid account-to-account: the lender, not the brand, holds the account
    from payeebench.cases import Case, honest_exec
    from meridian.core.edges import ASG
    b6 = next(b for b in world.brands.values() if b.genuine and b.structure == "S6")
    lt = next(t for t in b6.templates if "bnpl" in t.rails)
    lender = world.entities[lt.owner_lei]
    t6 = T_EXP_START - 10 * 86400
    sc6 = Scope.make(rails={"a2a_instant"}, currencies={b6.currency}, mccs={b6.mcc}, ceiling=300_000)
    asg = world.entity_issuers[b6.entity.lei].issue(ASG, b6.entity.lei_id, lender.lei_id, sc6, t6,
                                                    t6 + EDGE_LIFETIME, lender.rep)
    acct_l, te_l, _ = world.terminal(lender, t6)
    from payeebench.world import RouteTemplate
    tpl6a = RouteTemplate(world.next_id("rt"), b6.brand_id, "S6", ("a2a_instant",),
                          [world.brand_edge(b6), asg, te_l], acct_l, lender.rep, [], [], acct_l, te_l,
                          sc6.meet(world.brand_edge(b6).scope), lender.lei, lender.name)
    world.legit[b6.brand_id].append((tpl6a.scope, acct_l))
    pay6a = world.make_payment(tpl6a, "a2a_instant", 9000, T_EXP_START + 3600, rng)
    s6a = Case("S6a", "benign", "S6", "S6", "a2a_instant", b6.brand_id, b6.name, genuine_listing(b6, rng), pay6a,
               world.bundle_for(tpl6a, pay6a), *honest_exec(tpl6a), template=tpl6a)
    evaluate("S6", s6a)
    rows[-1]["case"] = "S6 (a2a)"

    # X1: a lookalike entity with its own valid IDs: "<Brand> Official", a
    # registered "<Brand> Official Store LLC", its own domain and chain
    bx = next(b for b in world.brands.values() if b.genuine and b.structure == "S1")
    att = kit.merchant(f"{bx.name}Official", f"{bx.name.lower()}-official.com", T_EXP_START - 40 * 86400, "card",
                       legal=f"{bx.name} Official Store LLC", display=f"{bx.name} Official", geo=bx.geo,
                       category=bx.category)
    atpl = att.templates[0]
    payx = world.make_payment(atpl, "card", 7000, T_EXP_START + 5 * 86400, rng)
    x1 = Case("X1", "X1", "affix", "S1", "card", bx.brand_id, bx.name,
              Listing(att.brand_id, att.name, att.domain, att.entity.name, att.entity.lei), payx,
              world.bundle_for(atpl, payx), *honest_exec(atpl), template=atpl)
    evaluate("X1", x1)

    # X2: seller substitution at a custodial marketplace
    br = next(b for b in world.brands.values() if b.genuine and b.structure == "S3")
    tpl = br.templates[0]
    plat_name = tpl.payee_operator
    plat = world.marketplaces[plat_name]
    t0 = T_EXP_START - 30 * 86400
    fake = kit.entity(f"{br.name} Official Store LLC", t0, br.geo)
    sc = tpl.scope
    store_f = plat.new_account("store", ns=f"mor:{plat.name}")
    f1 = plat.issue(AG, fake.lei_id, store_f, sc, t0, t0 + EDGE_LIFETIME, plat.key, delegate=True, signing_key=fake.rep)
    main = tpl.payee
    f2 = plat.issue(AG, store_f, main, sc, t0, t0 + EDGE_LIFETIME, plat.key, delegate=True)
    seller_f = plat.new_account("seller")
    f3 = plat.issue(SUB, main, seller_f, sc, t0, t0 + EDGE_LIFETIME, plat.key, subject=fake.lei_id)
    acct_f, te_f, _ = world.terminal(fake, t0)
    pay = world.make_payment(tpl, "card", 4500, T_EXP_START + 86400, rng)
    beta = BindingToken.issue(plat.key, pay)
    snaps = world.snapshots([*tpl.rap_edges, f1, f2, f3, te_f], pay.t)
    commits = [Commitment.issue(plat.key, REMIT, pay, main, seller_f, beta.digest),
               Commitment.issue(plat.key, PAYOUT, pay, seller_f, acct_f, beta.digest)]
    bundle_m = RouteBundle(RAP(list(tpl.rap_edges), snaps, beta), [f3], commits, te_f, snaps)
    bundle_b7 = RouteBundle(RAP([f1, f2], snaps, beta), [f3], commits, te_f, snaps)
    x2 = Case("X2", "X2", "seller-substitution", "S3", "card", br.brand_id, br.name,
              Listing(br.brand_id, f"{br.name} Official", f"{plat.name}.example", fake.name, fake.lei),
              pay, bundle_m, main, [(main, seller_f, plat.key), (seller_f, acct_f, plat.key)], acct_f, template=tpl)
    x2_b7 = replace(x2, bundle=bundle_b7)
    evaluate("X2", x2, bundle_m, x2_b7)

    x3 = next(c for c in gen_A6(world, kit, rng, 6) if c.variant == "card-payout-change")
    evaluate("X3", x3)
    x4 = next(c for c in gen_A8(world, kit, rng, 5) if c.variant == "geo")
    evaluate("X4", x4)
    x5 = gen_A13(world, kit, rng, 1)[0]
    evaluate("X5", x5)
    # X6: custodian gives no onward commitment (honest, but unverifiable)
    br6 = next(b for b in world.brands.values() if b.genuine and b.structure == "S1")
    tpl6 = br6.templates[0]
    pay6 = world.make_payment(tpl6, "card", 3000, T_EXP_START + 2 * 86400, rng)
    x6 = Case("X6", "X6", "no-commitment", "S1", "card", br6.brand_id, br6.name, genuine_listing(br6, rng), pay6,
              world.bundle_for(tpl6, pay6, drop_commitments=True), *honest_exec(tpl6), template=tpl6)
    evaluate("X6", x6, benign_no_div=True)
    df = pd.DataFrame(rows)
    write_table("f3_toy", df, "F3 toy check: B7 combined vs V1 original vs v2 core (hand-built structures)",
                "V1 original and the v2 core are given the correct brand; anchoring is V2's job. These are logic "
                "checks of the verifiers on constructed structures, not evidence about real systems. Correction to "
                "the blueprint's S6 row: B7 false-blocks the BNPL lender only when the lender is paid "
                "account-to-account, where B7's Verification of Payee against the brand's LEI fails because the "
                "lender owns the account (row 'S6 (a2a)'). On the card path B7 has no account-name check and allows "
                "the payment, so the blueprint's 'false block' for S6 holds only for account-to-account.",
                index=False)
    return df


def t4_mutations() -> pd.DataFrame:
    world = World(seed=SEED + 12).build()
    rng = random.Random(SEED + 12)
    from payeebench.cases import gen_benign
    rows = []
    cases = [c for c in gen_benign(world, rng, 2) if c.variant in ("S1", "S3") and c.bundle][:2]
    pol = Policy()
    for c in cases:
        jwt = f"eyJ.checkout.{c.payment.cart_digest}"
        m = ap2.build_mandate(jwt, c.payment, c.listing.display_name, c.bundle, c.intended)
        base = ap2.meridian_check(m, jwt, c.payment, c.bundle, c.intended, pol, world.trust).verdict
        rows.append({"protocol": "AP2", "structure": c.variant, "mutation": "(none)", "verdict": base,
                     "expected": ALLOW, "pass": base == ALLOW})
        for name, mm in ap2.mutations(m):
            v = ap2.meridian_check(mm, jwt, c.payment, c.bundle, c.intended, pol, world.trust).verdict
            exp = ALLOW if name == "payee.name" else "not ALLOW"
            rows.append({"protocol": "AP2", "structure": c.variant, "mutation": name, "verdict": v, "expected": exp,
                         "pass": (v == ALLOW) == (exp == ALLOW)})
        s = acp.checkout_session(f"cs_{c.case_id}", c.payment, c.listing.display_name, "pspone", c.bundle)
        d, allowance = acp.mint_delegated_payment(s, c.payment, c.bundle, c.intended, pol, world.trust)
        rows.append({"protocol": "ACP", "structure": c.variant, "mutation": "(none)", "verdict": d.verdict,
                     "expected": ALLOW, "pass": d.verdict == ALLOW and allowance["merchant_id"] == c.payment.payee})
        for name, ms in acp.mutations(s):
            d, _ = acp.mint_delegated_payment(ms, c.payment, c.bundle, c.intended, pol, world.trust)
            exp = ALLOW if name == "seller.name" else "not ALLOW"
            rows.append({"protocol": "ACP", "structure": c.variant, "mutation": name, "verdict": d.verdict,
                         "expected": exp, "pass": (d.verdict == ALLOW) == (exp == ALLOW)})
    # AP2 allowed-payee constraint with an empty merchant id
    allowed = ap2.AllowedPayees([ap2.Merchant("", "BrandX")])
    evil = ap2.Merchant("proc:evil/acct_1", "Evil")
    rows.append({"protocol": "AP2", "structure": "-", "mutation": "allowed_payees with empty id (reference check)",
                 "verdict": "accepts any payee" if ap2.reference_allowed_payee_check(allowed, evil) else "rejects",
                 "expected": "finding reproduced", "pass": ap2.reference_allowed_payee_check(allowed, evil)})
    rows.append({"protocol": "AP2", "structure": "-", "mutation": "allowed_payees with empty id (strict check)",
                 "verdict": "accepts any payee" if ap2.strict_allowed_payee_check(allowed, evil) else "rejects",
                 "expected": "rejects", "pass": not ap2.strict_allowed_payee_check(allowed, evil)})
    df = pd.DataFrame(rows)
    write_table("t4_mutations", df, "T4: mutation tests on AP2 v0.2 mandates and ACP checkout sessions", index=False)
    return df


def f5_split(per_size: int = 5, deadline: float = 5.0) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows = []
    for n in (8, 12, 16, 20, 24, 28, 32, 36, 40):
        m = max(2, n // 4)
        nodes, secs, timeouts, feas, ver = [], [], 0, 0, []
        for _ in range(per_size):
            items = rng.integers(10, 100, n).tolist()
            total = sum(items)
            caps = [total // m + (1 if j < total % m else 0) for j in range(m)]  # exact fit required
            t0 = time.perf_counter()
            assign, k, timed_out = find_split(items, caps, deadline_s=deadline)
            secs.append(time.perf_counter() - t0)
            nodes.append(k)
            timeouts += int(timed_out)
            feas += int(assign is not None)
            legs = [SplitLeg(f"d{i}", a, (f"e{(assign[i] if assign else i % m)}",)) for i, a in enumerate(items)]
            budgets = {f"e{j}": caps[j] for j in range(m)}
            t0 = time.perf_counter()
            for _ in range(200):
                verify_split(legs, budgets)
            ver.append((time.perf_counter() - t0) / 200 * 1e6)
        rows.append({"destinations n": n, "intermediaries m": m, "instances": per_size,
                     "search nodes (median)": int(np.median(nodes)), "search nodes (max)": int(max(nodes)),
                     "search s (max)": round(max(secs), 3), f"timeouts ({deadline:.0f} s)": timeouts,
                     "feasible": feas, "verify us (median)": round(float(np.median(ver)), 1)})
    df = pd.DataFrame(rows)
    write_table("f5_split", df, "F5: verifying a supplied split is linear; finding one is a bin-packing search",
                "Instances require an exact fit (sum of amounts equals total remaining budget).", index=False)
    return df


def run_toys() -> Dict:
    with Timer("F3 toy table"):
        f3 = f3_toy()
    with Timer("T4 mutation tests"):
        t4 = t4_mutations()
    with Timer("F5 split hardness"):
        f5 = f5_split()
    out = {"f3_matches_blueprint": f"{int(f3['matches blueprint'].sum())}/{len(f3)}",
           "f3_mismatches": f3[~f3["matches blueprint"]][["case", "B7 combined", "V1 original", "v2 core",
                                                          "blueprint (B7 / V1 / v2)"]].to_dict(orient="records"),
           "t4_pass": f"{int(t4['pass'].sum())}/{len(t4)}"}
    write_json("toys_summary", out)
    return out


if __name__ == "__main__":
    print(run_toys())
