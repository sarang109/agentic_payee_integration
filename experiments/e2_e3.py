"""E2 attack matrix and E3 legitimate structures (one bench run).

E2: A1-A13 against B1-B7 and M1-G1, M1, M2, M3; diversion success reported
    separately for in-model and premise-violation cases.
E3: false-block and step-up rates across legitimate structures.
Also produces the per-rail comparison used for RQ5 / H5 and paired exact
McNemar tests between configurations.
"""

from __future__ import annotations

import pandas as pd

import json
import os

from meridian.cba import CBAParams
from payeebench.cases import ATTACKS, PV_DESCRIPTIONS
from payeebench.configs import ALL_CONFIGS
from payeebench.runner import build_bench, run
from payeebench.world import STRUCTURES

from .common import QUICK, RAW, SEED, Timer, write_csv, write_json, write_table
from .stats import cluster_bootstrap, fmt_rate, paired_mcnemar, wilson

def calibrated_cba() -> CBAParams:
    path = os.path.join(RAW, "cba_calibration.json")
    if not os.path.exists(path):
        return CBAParams()
    with open(path) as fh:
        c = json.load(fh)
    return CBAParams(theta=c["theta"], tau=c["tau"], w_str=c["w_str"], w_vis=c["w_vis"], w_sem=c["w_sem"],
                     s_min=c["s_min"])


ORDER = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "M1-G1", "M1", "M2", "M3"]


def _counts(df: pd.DataFrame, col: str) -> pd.DataFrame:
    g = df.groupby(["kind", "config"])[col].agg(["sum", "count"]).reset_index()
    g["cell"] = g.apply(lambda r: f"{int(r['sum'])}/{int(r['count'])}", axis=1)
    t = g.pivot(index="kind", columns="config", values="cell")
    return t[[c for c in ORDER if c in t.columns]]


def _sort_kinds(t: pd.DataFrame) -> pd.DataFrame:
    key = {k: (k[0], int(k[1:]) if k[1:].isdigit() else 0) for k in t.index}
    return t.loc[sorted(t.index, key=lambda k: key[k])]


def run_e2_e3() -> dict:
    n_attack, n_benign, n_pv = (15, 20, 6) if QUICK else (60, 90, 20)
    with Timer(f"E2/E3 build bench (attack={n_attack}, benign/structure={n_benign}, pv={n_pv})"):
        world, cases = build_bench(seed=SEED, n_attack=n_attack, n_benign=n_benign, n_pv=n_pv)
    with Timer(f"E2/E3 run {len(cases)} payments x {len(ALL_CONFIGS)} configurations"):
        cba_params = calibrated_cba()
        recs = run(world, cases, ALL_CONFIGS, seed=SEED, progress=True, cba_params=cba_params)
    df = pd.DataFrame(recs)
    write_csv("payeebench_records", df)

    att = df[(df.kind != "benign") & (~df.premise_violation)]
    pv = df[df.premise_violation]
    ben = df[df.kind == "benign"]

    loss = _sort_kinds(_counts(att, "loss"))
    loss.index = [f"{k} {ATTACKS.get(k, '')}" for k in loss.index]
    write_table("e2_attack_matrix_loss", loss, "E2: diversion success (loss / attempts), in-model cases",
                "Exact counts over constructed cases. A loss means funds reached a terminal account that is not "
                "legitimate for the brand the user intended and the payment was not undone. Step-ups count as "
                "blocked here (the user declines); see e2_stepup for the share that relied on the user.")
    step = _sort_kinds(_counts(att, "step_up"))
    write_table("e2_attack_matrix_stepup", step, "E2: attacks stopped only by a step-up to the user (count / attempts)")
    pvt = _sort_kinds(_counts(pv, "loss"))
    pvt.index = [f"{k} {PV_DESCRIPTIONS.get(k, '')}" for k in pvt.index]
    write_table("e2_premise_violation", pvt, "E2: premise-violation partition, diversion success",
                "Reported as boundaries, not failures: each row breaks a standing assumption.")

    var = att.groupby(["kind", "variant", "config"])["loss"].agg(["sum", "count"]).reset_index()
    var["cell"] = var.apply(lambda r: f"{int(r['sum'])}/{int(r['count'])}", axis=1)
    vt = var.pivot(index=["kind", "variant"], columns="config", values="cell")
    write_table("e2_by_variant", vt[[c for c in ORDER if c in vt.columns]], "E2: loss by attack variant")

    # E3 -------------------------------------------------------------
    rows = []
    for (s, cfg), g in ben.groupby(["variant", "config"]):
        fb, su, n = int(g.false_block.sum()), int(g.step_up.sum()), len(g)
        rows.append({"structure": s, "config": cfg, "false_block": fb, "step_up": su, "n": n})
    e3 = pd.DataFrame(rows)
    fbt = e3.assign(cell=lambda d: d.false_block.astype(str) + "/" + d.n.astype(str)).pivot(
        index="structure", columns="config", values="cell")
    sut = e3.assign(cell=lambda d: d.step_up.astype(str) + "/" + d.n.astype(str)).pivot(
        index="structure", columns="config", values="cell")
    order_s = sorted(fbt.index, key=lambda s: int(s[1:]))
    fbt = fbt.loc[order_s, [c for c in ORDER if c in fbt.columns]]
    sut = sut.loc[order_s, [c for c in ORDER if c in sut.columns]]
    fbt.index = [f"{s} {STRUCTURES[s]}" for s in fbt.index]
    sut.index = [f"{s} {STRUCTURES[s]}" for s in sut.index]
    write_table("e3_false_block", fbt, "E3: false blocks on legitimate structures (count / payments)")
    write_table("e3_step_up", sut, "E3: step-ups on legitimate structures (count / payments)")

    # step-up causes and exposure split for MERIDIAN configs
    causes = ben[ben.step_up].groupby(["config", "stage"]).size().unstack(fill_value=0)
    write_table("e3_stepup_causes", causes, "E3: why benign payments were stepped up (by verifier stage)")
    exp_rows = []
    for cfg in ["M1", "M2", "M3"]:
        g = ben[(ben.config == cfg) & (~ben.variant.isin(["S10", "S11"]))]
        for imp in (True, False):
            h = g[g.impersonated == imp]
            k = int((h.step_up & (h.stage == "cba")).sum())
            exp_rows.append({"config": cfg, "brand impersonated": imp, "CBA step-ups": fmt_rate(k, len(h))})
    write_table("e3_stepup_exposure", pd.DataFrame(exp_rows), "E3: CBA step-up rate by brand exposure to impersonation",
                "Brands outside S10 (new) and S11 (no credentials). Wilson 95% intervals.", index=False)

    # rates with cluster bootstrap by merchant topology (structure x brand)
    boot_rows = []
    for cfg in ORDER:
        g = ben[(ben.config == cfg) & (~ben.variant.isin(["S10", "S11"]))]
        cl = (g.variant + "|" + g.intended).tolist()
        fb = cluster_bootstrap(g.false_block.astype(float).tolist(), cl, seed=SEED)
        su = cluster_bootstrap(g.step_up.astype(float).tolist(), cl, seed=SEED)
        boot_rows.append({"config": cfg, "n": len(g), "false_block": f"{fb[0]:.4f} [{fb[1]:.4f}, {fb[2]:.4f}]",
                          "step_up": f"{su[0]:.4f} [{su[1]:.4f}, {su[2]:.4f}]"})
    write_table("e3_rates_bootstrap", pd.DataFrame(boot_rows),
                "E3: benign false-block and step-up rates (S1-S9, S12, S13), cluster bootstrap 95% CI",
                index=False)

    # paired comparisons ------------------------------------------------
    piv = att.pivot_table(index="case_id", columns="config", values="loss", aggfunc="first")
    kinds = att.drop_duplicates("case_id").set_index("case_id")["kind"]
    tests = []
    for a, b, scope in [("M2", "M1", ["A1", "A2"]), ("M1", "M1-G1", ["A6", "A13"]), ("M3", "M2", ["A11", "A12"]),
                        ("M1", "B7", None), ("M2", "B7", None), ("M3", "B7", None), ("M3", "M1", None)]:
        ids = piv.index if scope is None else [i for i in piv.index if kinds[i] in scope]
        r = paired_mcnemar(piv.loc[ids, a].astype(bool), piv.loc[ids, b].astype(bool))
        tests.append({"A": a, "B": b, "cases": "all in-model" if scope is None else "+".join(scope),
                      "n": len(ids), "loss under A only": r["x_only"], "loss under B only": r["y_only"],
                      "p (exact McNemar)": f"{r['p_value']:.3g}"})
    write_table("e2_mcnemar", pd.DataFrame(tests), "E2: paired exact McNemar tests on loss", index=False)

    # RQ5 / H5: per rail ----------------------------------------------
    rail_rows = []
    for (rail, cfg), g in df[~df.premise_violation].groupby(["rail", "config"]):
        a = g[g.kind != "benign"]
        b = g[g.kind == "benign"]
        rail_rows.append({"rail": rail, "config": cfg, "attack_loss": f"{int(a.loss.sum())}/{len(a)}",
                          "loss_rate": a.loss.mean() if len(a) else float("nan"),
                          "benign_step_up": b.step_up.mean() if len(b) else float("nan"),
                          "benign_false_block": b.false_block.mean() if len(b) else float("nan"),
                          "p95_decision_ms": g.decision_ms.quantile(0.95)})
    rt = pd.DataFrame(rail_rows)
    write_table("rq5_per_rail", rt.round(4), "RQ5: per-rail security / utility by configuration", index=False)

    summary = hypotheses_from(df, rt)
    summary["cba_params"] = {"theta": cba_params.theta, "tau": cba_params.tau}
    summary["n_cases"] = int(df.case_id.nunique())
    summary["n_records"] = len(df)
    write_json("e2_e3_summary", summary)
    return summary


def hypotheses_from(df: pd.DataFrame, rt: pd.DataFrame) -> dict:
    att = df[(df.kind != "benign") & (~df.premise_violation)]
    ben = df[df.kind == "benign"]
    out = {}
    v1_classes = ["A3", "A4", "A5", "A7", "A8"]
    m1 = att[(att.config == "M1") & att.kind.isin(v1_classes)]
    base_hits = {b: int(att[(att.config == b) & att.kind.isin(v1_classes)].loss.sum()) for b in ["B1", "B2", "B3", "B4", "B5"]}
    core = ben[(ben.config == "M1") & ben.variant.isin(["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S12", "S13"])]
    fb = int(core.false_block.sum())
    out["H1"] = {
        "m1_loss_on_v1_classes": f"{int(m1.loss.sum())}/{len(m1)}",
        "baseline_losses_on_v1_classes": base_hits,
        "m1_false_block_rate": fmt_rate(fb, len(core)),
        "supported": bool(m1.loss.sum() == 0 and all(v > 0 for v in base_hits.values()) and fb / max(1, len(core)) <= 0.01),
    }
    lk = att[att.kind.isin(["A1", "A2"])].pivot_table(index="case_id", columns="config", values="loss", aggfunc="first")
    r = paired_mcnemar(lk["M2"].astype(bool), lk["M1"].astype(bool))
    b2 = ben[(ben.config == "M2") & ~ben.variant.isin(["S10", "S11"])]
    cba_su = int((b2.step_up & (b2.stage == "cba")).sum())
    out["H2"] = {
        "m2_loss_A1_A2": f"{int(lk['M2'].sum())}/{len(lk)}", "m1_loss_A1_A2": f"{int(lk['M1'].sum())}/{len(lk)}",
        "mcnemar_p": r["p_value"], "benign_cba_step_up": fmt_rate(cba_su, len(b2)),
        "all_benign_step_up_m2": fmt_rate(int(b2.step_up.sum()), len(b2)),
        "supported": bool(lk["M2"].sum() < lk["M1"].sum() and r["p_value"] < 0.05 and cba_su / max(1, len(b2)) <= 0.05),
    }
    a11 = att[(att.kind == "A11") & (att.config == "M3") & (att.rail.isin(["card", "psp_token"]))]
    a12 = att[(att.kind == "A12")]
    out["H3_bench_part"] = {
        "M3_card_A11_detected_and_undone": f"{int(a11.undone.sum())}/{len(a11)}",
        "A12_loss_M2_vs_M3": {c: f"{int(a12[a12.config == c].loss.sum())}/{len(a12[a12.config == c])}" for c in ["M2", "M3"]},
        "A12_M3_modes": a12[a12.config == "M3"].groupby("mode").size().to_dict(),
        "note": "full H3 decision uses E6",
    }
    best = {}
    for rail, g in rt[rt.config.isin(["M1", "M2", "M3"])].groupby("rail"):
        g = g.sort_values(["loss_rate", "benign_step_up", "p95_decision_ms"])
        best[rail] = g.iloc[0]["config"]
    out["H5"] = {"best_meridian_config_per_rail": best, "supported": len(set(best.values())) > 1}
    return out


if __name__ == "__main__":
    print(run_e2_e3())
