"""Planned ablations.

1. bilateral vs one-sided edges: a processor that controls only one endpoint
   tries to claim a platform store (unilateral claim), under V1 original and
   under the v2 core;
2. no scope meet: scope-abuse attacks (A8) with the meet disabled;
3. status freshness rho from seconds to days: reuse of a revoked delegation
   whose revocation is r seconds old;
4. probation Delta: see E5;  5. observers and collusion: see E6;
6. RAP vs directory under outage and a lying directory: see E1.
"""

from __future__ import annotations

import math
import random
from typing import Dict

import numpy as np
import pandas as pd

from meridian.core.decision import ALLOW
from meridian.core.edges import AG
from meridian.core.pav import RAP, BindingToken, pav
from meridian.core.policy import Policy
from meridian.core.routes import PAYOUT, Commitment, RouteBundle, verify_route
from payeebench.cases import AttackerKit, _reseller, gen_A8
from payeebench.runner import run
from payeebench.world import DAY, EDGE_LIFETIME, HOUR, T_EXP_START, World

from .common import QUICK, SEED, Timer, write_json, write_table
from .e2_e3 import calibrated_cba


def unilateral_claim(n: int) -> pd.DataFrame:
    """A compromised processor issues an L2->L3 edge from a brand's store at
    a marketplace to an account it operates, without the marketplace."""
    world = World(seed=SEED + 21).build()
    rng = random.Random(SEED + 21)
    kit = AttackerKit(world, rng)
    rows = []
    stores = [(b, t) for b in world.brands.values() if b.genuine for t in b.templates if t.structure == "S3"]
    for i in range(n):
        br, tpl = stores[i % len(stores)]
        psp = world.psps["psptwo"]
        t = T_EXP_START + rng.randrange(0, 20 * DAY)
        mule = kit.entity("Processor Mule LLC", t - 30 * DAY)
        acct_p = psp.new_account()
        store = tpl.rap_edges[1].dst
        # one-sided: the processor authorises (as operator of the destination)
        # and nobody from the platform side accepts
        forged = psp.issue(AG, store, acct_p, tpl.scope, t - DAY, t + EDGE_LIFETIME, psp.key, delegate=True)
        acct, te, _ = world.terminal(mule, t - 30 * DAY)
        pay = world.make_payment(tpl, "card", 5000, t, rng, payee=acct_p)
        beta = BindingToken.issue(psp.key, pay)
        edges = [tpl.rap_edges[0], tpl.rap_edges[1], forged]
        snaps = world.snapshots(edges + [te], t)
        rap = RAP(edges, snaps, beta)
        bundle = RouteBundle(rap, [], [Commitment.issue(psp.key, PAYOUT, pay, acct_p, acct, beta.digest)], te, snaps)
        for bilateral in (True, False):
            p1 = Policy(grammar=False, require_acceptance=bilateral)
            p2 = Policy(require_acceptance=bilateral)
            d1 = pav(rap, pay, br.brand_id, p1, world.trust)
            d2 = verify_route(bundle, pay, br.brand_id, p2, world.trust)
            rows.append({"edges": "bilateral" if bilateral else "one-sided", "V1 original": d1.verdict,
                         "v2 core": d2.verdict, "v2 reason": ";".join(d2.reasons[:1])})
    df = pd.DataFrame(rows)
    out = df.groupby("edges").agg(attempts=("V1 original", "size"),
                                  v1_loss=("V1 original", lambda s: int((s == ALLOW).sum())),
                                  v2_loss=("v2 core", lambda s: int((s == ALLOW).sum()))).reset_index()
    out.columns = ["edges", "attempts", "diverted under V1 original", "diverted under v2 core"]
    return out


def scope_meet(n: int) -> pd.DataFrame:
    world = World(seed=SEED + 22).build()
    rng = random.Random(SEED + 22)
    kit = AttackerKit(world, rng)
    cases = gen_A8(world, kit, rng, n)
    rows = []
    for meet in (True, False):
        w2 = world
        recs = run(w2, cases, ["M1"], use_scope_meet=meet, seed=SEED, cba_params=calibrated_cba())
        df = pd.DataFrame(recs)
        for v, g in df.groupby("variant"):
            rows.append({"scope meet": "on" if meet else "off (ablation)", "variant": v,
                         "loss": f"{int(g.loss.sum())}/{len(g)}"})
    t = pd.DataFrame(rows).pivot(index="variant", columns="scope meet", values="loss")
    return t


def rho_sweep(n: int) -> pd.DataFrame:
    world = World(seed=SEED + 23).build()
    rng = random.Random(SEED + 23)
    targets = [b for b in world.brands.values() if b.genuine and b.structure in ("S1", "S3", "S4")]
    from meridian.core.scope import Scope
    trials = []
    for i in range(n):
        br = targets[i % len(targets)]
        t = T_EXP_START + rng.randrange(0, 20 * DAY)
        sc = Scope.make(rails={"card"}, currencies={br.currency}, mccs={br.mcc}, geos={br.geo}, ceiling=500_000)
        tpl, e1, ei = _reseller(world, br, t - 100 * DAY, rng, sc, f"{br.name} Ex-Reseller Ltd")
        age = int(math.exp(rng.uniform(math.log(10), math.log(30 * DAY))))
        ei.status_list.revoke(e1.status.index, t - age)
        pay = world.make_payment(tpl, "card", 4000, t, rng)
        # the attacker staples the freshest snapshot that predates revocation
        bundle = world.bundle_for(tpl, pay, snap_t=t - age - 1)
        trials.append((age, bundle, pay, br.brand_id))
    rows = []
    for rho in (0, 60, 300, HOUR, DAY, 7 * DAY):
        pol = Policy(grammar=False, rho=rho)
        acc = [int(pav(b.rap, p, a, pol, world.trust).verdict == ALLOW) for (_, b, p, a) in trials]
        ages = np.array([a for a, *_ in trials])
        rows.append({"rho": rho, "reuse accepted": f"{sum(acc)}/{len(acc)}",
                     "accepted share": round(float(np.mean(acc)), 3),
                     "share of revocations younger than rho": round(float(np.mean(ages <= rho)), 3)})
    return pd.DataFrame(rows)


def run_ablations() -> Dict:
    n = 10 if QUICK else 40
    with Timer("ablation 1: bilateral vs one-sided edges"):
        a1 = unilateral_claim(n)
    write_table("ablation1_bilateral", a1, "Ablation 1: unilateral claim by a processor controlling one endpoint",
                index=False)
    with Timer("ablation 2: scope meet"):
        a2 = scope_meet(n)
    write_table("ablation2_scope_meet", a2, "Ablation 2: scope abuse (A8) with and without the scope meet (M1)")
    with Timer("ablation 3: status freshness rho"):
        a3 = rho_sweep(4 * n)
    write_table("ablation3_rho", a3, "Ablation 3: reuse of a revoked delegation vs freshness bound rho (V1)",
                "Revocation ages are log-uniform between 10 s and 30 days; the attacker staples the freshest "
                "pre-revocation snapshot.", index=False)
    out = {"ablation1": a1.to_dict(orient="records"), "ablation3": a3.to_dict(orient="records"),
           "see_also": {"4": "E5 probation sweep", "5": "E6 observers and collusion", "6": "E1 outage and lying directory"}}
    write_json("ablations_summary", out)
    return out


if __name__ == "__main__":
    print(run_ablations())
