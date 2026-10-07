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
                     s_min=c["s_min"], use=tuple(c.get("use", ("str", "vis", "sem"))))


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

    # the cost of the loss reduction, side by side: attacks lost against legitimate payments the user had to confirm
    n_att = att.case_id.nunique()
    core = ben[~ben.variant.isin(["S10", "S11"])]
    cb_rows = []
    for cfg in ["B7", "M1", "M2", "M3"]:
        la = att[att.config == cfg]
        row = {"config": cfg, "in-model attacks lost": f"{int(la.loss.sum())}/{n_att}"}
        for label, d in (("established structures (S1-S9, S12, S13)", core),
                         ("S10 newly onboarded", ben[ben.variant == "S10"]),
                         ("S11 no credentials", ben[ben.variant == "S11"])):
            g = d[d.config == cfg]
            row[f"step-ups, {label}"] = f"{int(g.step_up.sum())}/{len(g)}"
        for s_id in ("S9", "S12", "S1"):
            g = ben[(ben.config == cfg) & (ben.variant == s_id)]
            row[f"step-ups, {s_id} {STRUCTURES[s_id]}"] = f"{int(g.step_up.sum())}/{len(g)}"
        cb_rows.append(row)
    write_table("e3_cost_vs_benefit", pd.DataFrame(cb_rows),
                "E3: attacks lost next to legitimate payments stepped up to the user",
                "Exact counts. A step-up is a legitimate payment the user must confirm, so M2's lower loss comes "
                "with the step-up cost on the right; S11 steps up for every configuration that requires a credential. "
                "Read this table before quoting M2's advantage over B7.", index=False)

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
    write_table("rq5_pareto", pareto_table(rt), "RQ5 (exploratory): security versus friction per rail",
                "Not a pre-registered analysis. A configuration is on the frontier when no other configuration has "
                "both lower or equal loss and lower or equal benign step-up, with one strictly lower. Rails with no "
                "attack cases are omitted.", index=False)
    with Timer("E2 AIP-Bench external scenarios (exploratory)"):
        summary["aip_external_loss"] = aip_external(8 if QUICK else 30)
    with Timer("RQ5 BNPL supplement (exploratory)"):
        bn = bnpl_supplement(15 if QUICK else 60, 20 if QUICK else 90)
    rt_bn = pd.concat([rt[rt.rail != "bnpl"], pd.DataFrame(bn["rows"])], ignore_index=True)
    summary["H5_exploratory_with_bnpl_supplement"] = {k: v for k, v in h5_verdict(rt_bn).items()
                                                      if not k.startswith("legacy")}
    write_table("rq5_pareto_with_bnpl", pareto_table(rt_bn[rt_bn.rail == "bnpl"]),
                "RQ5 (exploratory): BNPL frontier from the supplement", index=False)
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
        "security_part_supported": bool(lk["M2"].sum() < lk["M1"].sum() and r["p_value"] < 0.05),
        "note": "the step-up target is measured in E4 (held-out brands); the bench value above is context",
    }
    a11 = att[(att.kind == "A11") & (att.config == "M3") & (att.rail.isin(["card", "psp_token"]))]
    a12 = att[(att.kind == "A12")]
    out["H3_bench_part"] = {
        "M3_card_A11_detected_and_undone": f"{int(a11.undone.sum())}/{len(a11)}",
        "A12_loss_M2_vs_M3": {c: f"{int(a12[a12.config == c].loss.sum())}/{len(a12[a12.config == c])}" for c in ["M2", "M3"]},
        "A12_M3_modes": a12[a12.config == "M3"].groupby("mode").size().to_dict(),
        "note": "full H3 decision uses E6",
    }
    out["H5"] = h5_verdict(rt)
    return out


def best_sets(rt: pd.DataFrame, configs=("M1", "M2", "M3")) -> dict:
    """Per rail with attack data: the configurations with the lowest loss
    rate and, among those, the lowest benign step-up rate. Exact ties are
    kept as ties; decision latency is not used to break them."""
    out = {}
    for rail, g in rt[rt.config.isin(configs)].groupby("rail"):
        if g.loss_rate.isna().all():
            continue
        g = g[g.loss_rate == g.loss_rate.min()]
        g = g[g.benign_step_up == g.benign_step_up.min()]
        out[rail] = sorted(g.config)
    return out


def h5_verdict(rt: pd.DataFrame) -> dict:
    """Pre-registered rule: supported if the configuration with the lowest
    (loss, step-up) on one rail differs from the one on another. With ties
    this means: no configuration is among the best on every rail that has
    attack data. Rails with no attack cases cannot rank configurations on
    loss and are left out."""
    best = best_sets(rt)
    common = set.intersection(*(set(v) for v in best.values())) if best else set()
    no_attacks = sorted(set(rt.rail) - set(best))
    # the earlier computation, kept for the record: sorted by loss, step-up
    # and decision latency, with NaN loss sorting last
    legacy = {}
    for rail, g in rt[rt.config.isin(["M1", "M2", "M3"])].groupby("rail"):
        legacy[rail] = g.sort_values(["loss_rate", "benign_step_up", "p95_decision_ms"]).iloc[0]["config"]
    return {"best_meridian_configs_per_rail": best, "rails_without_attack_cases": no_attacks,
            "best_on_every_rail": sorted(common), "supported": bool(best) and not common,
            "legacy_latency_tiebreak": legacy, "legacy_supported": len(set(legacy.values())) > 1}


def pareto_table(rt: pd.DataFrame, configs=("B7", "M1", "M2", "M3")) -> pd.DataFrame:
    """Exploratory (not pre-registered): per rail, configurations not
    dominated on (loss rate, benign step-up rate)."""
    rows = []
    for rail, g in rt[rt.config.isin(configs)].groupby("rail"):
        g = g.dropna(subset=["loss_rate"])
        for _, r in g.iterrows():
            dominated = any((o.loss_rate <= r.loss_rate and o.benign_step_up <= r.benign_step_up and
                             (o.loss_rate < r.loss_rate or o.benign_step_up < r.benign_step_up))
                            for _, o in g.iterrows())
            rows.append({"rail": rail, "config": r.config, "attack loss": r.attack_loss,
                         "loss rate": round(r.loss_rate, 4), "benign step-up": round(r.benign_step_up, 4),
                         "on the frontier": "yes" if not dominated else ""})
    return pd.DataFrame(rows)


def aip_external(n_per: int = 30) -> dict:
    """AIP-Bench payee-diversion scenarios replayed on a separate world
    (exploratory; the attack specification is external, the instance is
    generated)."""
    import random

    from payeebench.cases import AIP_SCENARIOS, AttackerKit, gen_aip_external
    from payeebench.world import World

    world = World(seed=SEED).build()
    rng = random.Random(SEED * 1000 + 41)
    cases = gen_aip_external(world, AttackerKit(world, rng), rng, n_per)
    df = pd.DataFrame(run(world, cases, ALL_CONFIGS, seed=SEED, cba_params=calibrated_cba()))
    write_csv("e2_aip_external_records", df)
    df["scenario"] = df.variant.str.rsplit(":", n=1).str[0]
    g = df.groupby(["scenario", "config"]).loss.agg(["sum", "count"]).reset_index()
    g["cell"] = g.apply(lambda r: f"{int(r['sum'])}/{int(r['count'])}", axis=1)
    t = g.pivot(index="scenario", columns="config", values="cell")
    t = t[[c for c in ORDER if c in t.columns]]
    t.index = [f"{k}: {AIP_SCENARIOS[k]}" for k in t.index]
    write_table("e2_aip_external", t, "E2 (exploratory): payee-diversion scenarios specified by AIP-Bench",
                "Scenarios from AIP-Bench (arXiv 2607.21824; Hugging Face anonymos-2321135/aip-bench, CC BY 4.0, "
                "revision eaa6015). The scenario fixes what the attacker controls; brands, rails and attacker "
                "infrastructure come from the PayeeBench generator, so this reduces but does not remove the "
                "circularity of a self-built bench. AIP-Bench scenarios that steal the payer's credentials "
                "(A-AP2-5, A-AP2-15) or forge mandates (A-AP2-4) are outside MERIDIAN's object and not replayed.")
    return {c: int(df[df.config == c].loss.sum()) for c in ALL_CONFIGS}


def bnpl_supplement(n_attack: int = 60, n_benign: int = 90) -> dict:
    """BNPL attack set on its own world (the pre-registered bench has no
    attacks on the BNPL rail). Exploratory: added after the pre-registered
    run, reported separately and not used for the H5 verdict."""
    import random

    from payeebench.cases import AttackerKit, gen_benign, gen_bnpl
    from payeebench.world import World

    world = World(seed=SEED).build()
    rng = random.Random(SEED * 1000 + 29)
    kit = AttackerKit(world, rng)
    ben = [c for c in gen_benign(world, rng, n_benign) if c.variant == "S6"]
    att = gen_bnpl(world, kit, rng, n_attack)
    df = pd.DataFrame(run(world, ben + att, ALL_CONFIGS, seed=SEED, cba_params=calibrated_cba()))
    write_csv("rq5_bnpl_records", df)
    a = df[df.kind != "benign"]
    t = _sort_kinds(_counts(a, "loss"))
    t.index = [f"{k} {ATTACKS.get(k, '')}" for k in t.index]
    b = df[df.kind == "benign"]
    su = b.groupby("config").step_up.agg(["sum", "count"])
    t.loc["benign step-ups (S6)"] = [f"{int(su.loc[c, 'sum'])}/{int(su.loc[c, 'count'])}" for c in t.columns]
    write_table("rq5_bnpl_supplement", t, "RQ5 supplement: attacks on the BNPL route (exploratory, separate world)",
                "Not part of the pre-registered bench. A3/A4 swap the payee, A11 is a first-hop mismatch after "
                "authorization, A13 the lender's PSP pays out to an insider. M3 does not undo A11 or A13 here: the "
                "modelled BNPL void success (0.98, config/rails.yaml) is below 1 - eps = 0.99, so POST is not "
                "POST-safe under Theorem 3 and RWS falls back to PRE, which detects but cannot undo.")
    rows = []
    for cfg, g in df.groupby("config"):
        aa, bb = g[g.kind != "benign"], g[g.kind == "benign"]
        rows.append({"rail": "bnpl", "config": cfg, "attack_loss": f"{int(aa.loss.sum())}/{len(aa)}",
                     "loss_rate": aa.loss.mean(), "benign_step_up": bb.step_up.mean(),
                     "benign_false_block": bb.false_block.mean(), "p95_decision_ms": g.decision_ms.quantile(0.95)})
    return {"rows": rows, "loss": {c: int(df[(df.kind != "benign") & (df.config == c)].loss.sum())
                                   for c in ALL_CONFIGS}}


if __name__ == "__main__":
    print(run_e2_e3())
