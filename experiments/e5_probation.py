"""E5 probation sweep: Delta from 0 to 14 days.

Attack success of freshly minted fake delegations (A9) for a rushing and a
patient attacker, against the delay imposed on legitimate new edges
(newly onboarded merchants step up or are capped while in probation).
Also sweeps the brand monitor's reaction time and the probation cap.
"""

from __future__ import annotations

import random

import pandas as pd

from payeebench.cases import AttackerKit, gen_A9, gen_benign
from payeebench.runner import run
from payeebench.world import DAY, HOUR, World

from .common import FIGURES, QUICK, SEED, Timer, write_csv, write_json, write_table
from .e2_e3 import calibrated_cba
from .stats import fmt_rate

DELTAS = [0, HOUR, 6 * HOUR, DAY, 3 * DAY, 7 * DAY, 14 * DAY]


def _one(delta: int, monitor_median: float, n_attack: int, n_benign: int, cap: int = 0, seed: int = SEED):
    world = World(seed=seed, delta=delta, monitor_median_s=monitor_median).build()
    rng = random.Random(seed * 31 + 5)
    kit = AttackerKit(world, rng)
    cases = [c for c in gen_benign(world, rng, n_benign) if c.variant in ("S10", "S1", "S3", "S12")]
    rush = gen_A9(world, kit, rng, n_attack, strategy="rush")
    patient = gen_A9(world, kit, rng, n_attack, strategy="patient")
    for c in patient:
        c.variant = "patient"
        c.case_id = c.case_id.replace("A9", "A9p")
    for c in rush:
        c.variant = "rush"
    recs = run(world, cases + rush + patient, ["M1", "M2"], delta=delta, probation_cap=cap, seed=seed,
               cba_params=calibrated_cba())
    df = pd.DataFrame(recs)
    out = {}
    for strat in ("rush", "patient"):
        a = df[(df.kind == "A9") & (df.variant == strat) & (df.config == "M2")]
        out[f"A9 {strat} success"] = fmt_rate(int(a.loss.sum()), len(a), interval=False)
        out[f"_{strat}_rate"] = a.loss.mean()
        out[f"A9 {strat} loss amount"] = int(a[a.loss].amount.sum())
    b = df[(df.kind == "benign") & (df.config == "M2")]
    new = b[b.variant == "S10"]
    out["S10 new-merchant step-up"] = fmt_rate(int((new.step_up & (new.stage == "mtl")).sum()), len(new),
                                               interval=False)
    out["_new_rate"] = (new.step_up & (new.stage == "mtl")).mean()
    old = b[b.variant != "S10"]
    out["established step-up (probation)"] = fmt_rate(int((old.step_up & (old.stage == "mtl")).sum()), len(old),
                                                      interval=False)
    return out, df


def run_e5() -> dict:
    n_attack, n_benign = (12, 15) if QUICK else (60, 60)
    rows = []
    with Timer("E5 probation sweep"):
        for d in DELTAS:
            out, df = _one(d, 6 * HOUR, n_attack, n_benign)
            rows.append({"Delta": _fmt(d), "Delta_s": d, **out})
    t = pd.DataFrame(rows)
    write_csv("e5_probation_sweep", t)
    write_table("e5_probation", t[[c for c in t.columns if not c.startswith("_") and c != "Delta_s"]],
                "E5: probation Delta vs fake-delegation success (M2) and cost to new merchants",
                "Monitor reaction: lognormal, median 6 h. Rush attacker uses the fake edge after a lognormal delay "
                "(median ~8 h); patient attacker waits Delta + 1-3 h. Exact counts.", index=False)

    mrows = []
    with Timer("E5 monitor reaction sweep at Delta = 3 days"):
        for med in [HOUR, 6 * HOUR, DAY, 3 * DAY, 7 * DAY]:
            out, _ = _one(3 * DAY, med, n_attack, max(5, n_benign // 3))
            mrows.append({"monitor median": _fmt(med), "A9 rush success": out["A9 rush success"],
                          "A9 patient success": out["A9 patient success"]})
    write_table("e5_monitor_reaction", pd.DataFrame(mrows), "E5: monitor reaction time vs success (Delta = 3 days)",
                index=False)

    crows = []
    with Timer("E5 probation cap sweep at Delta = 3 days"):
        for cap in [0, 2_000, 10_000, 50_000]:
            out, _ = _one(3 * DAY, 6 * HOUR, n_attack, max(5, n_benign // 3), cap=cap)
            crows.append({"cap (minor units)": cap, "A9 rush success": out["A9 rush success"],
                          "A9 rush loss amount": out["A9 rush loss amount"],
                          "S10 new-merchant step-up": out["S10 new-merchant step-up"]})
    write_table("e5_cap", pd.DataFrame(crows), "E5: amount cap during probation instead of step-up", index=False)
    summary = {"sweep": t.drop(columns=[c for c in t.columns if c.startswith("_")]).to_dict(orient="records")}
    write_json("e5_summary", summary)
    return summary


def _fmt(s: int) -> str:
    if s == 0:
        return "0"
    if s % DAY == 0:
        return f"{s // DAY}d"
    return f"{s // HOUR}h"


if __name__ == "__main__":
    print(run_e5())
