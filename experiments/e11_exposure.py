"""E11: funded routes (F6) and hypothesis H6.

Custodians with varied hold time, discount rate, margin and bond handle a
Poisson stream of payments. A rational custodian steals what it holds the
first time doing so pays at the true detection probability q (see
meridian/core/exposure.py). The exposure-capped admission rule refuses a
payment that would take the custodian's in-flight exposure past the cap
computed from the detection probability q_hat the verifier assumes.

Everything here is a simulation of an economic model; no custodian, rail or
detection process is measured. q cannot be measured in the sandbox, so the
experiment sweeps it. Every parameter comes from the `experiment` block of
preregistration/hypotheses_v2.yaml, which must be locked first (LOCK_V2).

Populations
  provisioned    bond chosen so the admission cap equals capacity_factor times
                 the custodian's mean exposure at the rule's q_hat
  unprovisioned  bond a lognormal multiple of mean exposure, independent of the
                 rule (shows what the rule does to custodians it was not
                 provisioned for)

Rules (q_hat): oracle (= q), floor (0.3), optimistic (0.8). Admission is `on`
(the rule) or `off` (everything is accepted).

One arrival path per custodian is reused across every rule, q and population,
so comparisons are paired. A custodian's deviation condition depends on the
exposure only, so the loss for any true q is read off the record-high
exposures of the path (the first record above the deterrence cap).
"""

from __future__ import annotations

import bisect
import copy
import heapq
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from meridian.core.exposure import (Custodian, admission_cap, coalition_q, coalition_rational,
                                    deviation_threshold, hold_time_threshold, rational_to_deviate, required_bond)

from . import prereg
from .common import QUICK, Timer, write_csv, write_json, write_table
from .stats import wilson

RULES = ("oracle", "floor", "optimistic")


# ------------------------------------------------------------------ draws and paths

@dataclass
class Draw:
    idx: int
    hold: float
    beta: float
    lam: float  # payments per day
    mu: float  # mean exposure, cents
    margin: float  # honest profit per day, cents
    bond_unprov: float
    comp: bool  # compromised: deviates at t_comp whatever the incentives
    t_comp: float
    horizon: float
    warm: float
    seed: int


@dataclass
class Path:
    records: List[float]  # record-high exposures, increasing
    refused: int
    payments: int  # arrivals after warm-up
    comp_x: float  # exposure at the compromised custodian's deviation time


def amounts(p: dict, rng: np.random.Generator, n: int) -> np.ndarray:
    return np.clip(np.exp(rng.normal(p["lognormal_mu"], p["lognormal_sigma"], n)), p["floor"], p["cap"])


def mean_amount(p: dict, seed: int) -> float:
    return float(amounts(p, np.random.default_rng([seed, 99]), 400_000).mean())


def draw_custodians(P: dict, n: int, in_flight: int, seed: int, mean_amt: float) -> List[Draw]:
    rng = np.random.default_rng([seed, in_flight])
    c, u = P["custodian"], P["unprovisioned_population"]["bond_over_mean_exposure"]
    out = []
    for i in range(n):
        h = c["hold_days"]
        hold = float(np.clip(h["median"] * math.exp(h["sigma"] * rng.normal()), h["min"], h["max"]))
        r = math.exp(rng.uniform(math.log(c["discount_rate_per_day"]["low"]), math.log(c["discount_rate_per_day"]["high"])))
        phi = rng.uniform(c["margin_rate"]["low"], c["margin_rate"]["high"])
        lam = in_flight / hold
        mu = in_flight * mean_amt
        bond_u = mu * math.exp(math.log(u["median"]) + u["sigma"] * rng.normal())
        horizon, warm = P["horizon_hold_times"] * hold, P["warmup_hold_times"] * hold
        comp = bool(rng.random() < P["compromised"]["fraction"])
        out.append(Draw(i, hold, math.exp(-r), lam, mu, phi * lam * mean_amt, bond_u, comp,
                        float(rng.uniform(warm, horizon)), horizon, warm, int(rng.integers(2 ** 31))))
    return out


def run_path(P: dict, d: Draw, cap: Optional[float]) -> Path:
    """Replay the custodian's arrivals; ``cap=None`` accepts everything."""
    rng = np.random.default_rng(d.seed)
    n = int(rng.poisson(d.lam * d.horizon))
    times = np.sort(rng.random(n) * d.horizon)
    amts = amounts(P["payment_amount"], rng, n)
    held: List[Tuple[float, float]] = []
    X = 0.0
    records: List[float] = []
    refused = payments = 0
    comp_x: Optional[float] = None

    def release(upto: float) -> None:
        nonlocal X
        while held and held[0][0] <= upto:
            X -= heapq.heappop(held)[1]
        if not held:
            X = 0.0

    for t, a in zip(times.tolist(), amts.tolist()):
        if comp_x is None and d.t_comp <= t:
            release(d.t_comp)
            comp_x = X
        release(t)
        post = t >= d.warm
        if post:
            payments += 1
        if cap is None or X + a <= cap:
            heapq.heappush(held, (t + d.hold, a))
            X += a
            if not records or X > records[-1]:
                records.append(X)
        elif post:
            refused += 1
    if comp_x is None:
        release(d.t_comp)
        comp_x = X
    return Path(records, refused, payments, comp_x)


def crossing(path: Path, threshold: float) -> Optional[float]:
    """Exposure at the first time the custodian's exposure exceeds the
    threshold, or None if it never does."""
    i = bisect.bisect_right(path.records, threshold)
    return path.records[i] if i < len(path.records) else None


def q_hat_for(rule: str, q: float, P: dict) -> float:
    r = P["rules"][rule]["q_hat"]
    return q if r == "q" else float(r)


# ------------------------------------------------------------------ simulation

def _cust(d: Draw, bond: float) -> Custodian:
    return Custodian(f"c{d.idx}", bond, d.margin, d.beta, d.hold)


def _bootstrap_ratio(num: np.ndarray, den: np.ndarray, resamples: int, seed: int) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), (resamples, len(num)))
    s_n, s_d = num[idx].sum(axis=1), den[idx].sum(axis=1)
    r = s_n / np.maximum(s_d, 1)
    return float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975))


def simulate(P: dict, seed: int) -> Dict[str, pd.DataFrame]:
    """The whole population experiment. Pure: no files are read or written."""
    grid: List[float] = list(P["detection_grid"])
    f0 = float(P["capacity_factor"])
    n = int(P["custodians_per_cell"])
    boot_n = int(P["bootstrap"]["resamples"])
    mean_amt = mean_amount(P["payment_amount"], seed)
    ref = int(P["workloads"]["reference"])
    loss, refusal, cap_sens, bonds, tstar, comp, coal = [], [], [], [], [], [], []

    for wl in P["workloads"]["payments_in_flight"]:
        draws = draw_custodians(P, n, int(wl), seed, mean_amt)
        rational = [d for d in draws if not d.comp]
        compromised = [d for d in draws if d.comp]
        sum_mu = sum(d.mu for d in rational)
        off = {d.idx: run_path(P, d, None) for d in draws}

        # ---- provisioned: the bond makes the cap equal factor x mean exposure at q_hat
        def prov_bond(d: Draw, qh: float, f: float = f0) -> float:
            return required_bond(d.margin, d.beta, d.hold, qh, f * d.mu)

        on = {d.idx: run_path(P, d, f0 * d.mu) for d in draws}
        for f in [f0] + list(P["capacity_factors_reported"]):
            pf = on if f == f0 else {d.idx: run_path(P, d, f * d.mu) for d in draws}
            ref_n = np.array([pf[d.idx].refused for d in draws])
            tot_n = np.array([pf[d.idx].payments for d in draws])
            lo, hi = _bootstrap_ratio(ref_n, tot_n, boot_n, seed + 1)
            wl_lo, wl_hi = wilson(int(ref_n.sum()), int(tot_n.sum()))
            cap_sens.append({"workload": wl, "capacity factor": f, "payments": int(tot_n.sum()),
                             "refused": int(ref_n.sum()), "refusal rate": ref_n.sum() / max(1, tot_n.sum()),
                             "wilson lo": wl_lo, "wilson hi": wl_hi, "bootstrap lo": lo, "bootstrap hi": hi})
        for rule in RULES:
            for q in grid:
                qh = q_hat_for(rule, q, P)
                bnd = {d.idx: prov_bond(d, qh) for d in draws}
                ref_n = np.array([on[d.idx].refused for d in draws])
                tot_n = np.array([on[d.idx].payments for d in draws])
                lo, hi = _bootstrap_ratio(ref_n, tot_n, boot_n, seed + 2)
                refusal.append({"population": "provisioned", "workload": wl, "rule": rule, "q": q, "q_hat": qh,
                                "payments": int(tot_n.sum()), "refused": int(ref_n.sum()),
                                "refusal rate": ref_n.sum() / max(1, tot_n.sum()), "bootstrap lo": lo,
                                "bootstrap hi": hi})
                for adm, paths in (("on", on), ("off", off)):
                    dev, gross = 0, 0.0
                    for d in rational:
                        x = crossing(paths[d.idx], deviation_threshold(_cust(d, bnd[d.idx]), q))
                        if x is not None:
                            dev, gross = dev + 1, gross + x
                    loss.append({"population": "provisioned", "workload": wl, "rule": rule, "admission": adm,
                                 "q": q, "q_hat": qh, "rational custodians": len(rational), "deviating": dev,
                                 "gross loss / mean exposure": gross / sum_mu if sum_mu else 0.0})
                    cx = [(paths[d.idx].comp_x, bnd[d.idx]) for d in compromised]
                    comp.append(_comp_row("provisioned", wl, rule, adm, q, qh, cx, sum(d.mu for d in compromised)))
                ex = f0 * np.array([d.mu for d in draws])
                ts = [hold_time_threshold(_cust(d, bnd[d.idx]), float(e), q) for d, e in zip(draws, ex)]
                tstar.append(_tstar_row("provisioned", wl, rule, q, ts, [d.hold for d in draws]))
        for qh in grid:
            bs = np.array([prov_bond(d, qh) / d.mu for d in draws])
            bonds.append({"workload": wl, "q_hat": qh, "bond / mean exposure (median)": float(np.median(bs)),
                          "p25": float(np.quantile(bs, 0.25)), "p75": float(np.quantile(bs, 0.75)),
                          "share where deterrence (not coverage) binds": float(np.mean(bs > f0 + 1e-9))})

        # ---- unprovisioned: bond independent of the rule
        paths_u = {qh: {d.idx: run_path(P, d, admission_cap(_cust(d, d.bond_unprov), qh)) for d in draws}
                   for qh in sorted({q_hat_for(r, q, P) for r in RULES for q in grid})}
        for rule in RULES:
            for q in grid:
                qh = q_hat_for(rule, q, P)
                on_u = paths_u[qh]
                ref_n = np.array([on_u[d.idx].refused for d in draws])
                tot_n = np.array([on_u[d.idx].payments for d in draws])
                lo, hi = _bootstrap_ratio(ref_n, tot_n, boot_n, seed + 3)
                refusal.append({"population": "unprovisioned", "workload": wl, "rule": rule, "q": q, "q_hat": qh,
                                "payments": int(tot_n.sum()), "refused": int(ref_n.sum()),
                                "refusal rate": ref_n.sum() / max(1, tot_n.sum()), "bootstrap lo": lo,
                                "bootstrap hi": hi})
                for adm, paths in (("on", on_u), ("off", off)):
                    dev, gross = 0, 0.0
                    for d in rational:
                        x = crossing(paths[d.idx], deviation_threshold(_cust(d, d.bond_unprov), q))
                        if x is not None:
                            dev, gross = dev + 1, gross + x
                    loss.append({"population": "unprovisioned", "workload": wl, "rule": rule, "admission": adm,
                                 "q": q, "q_hat": qh, "rational custodians": len(rational), "deviating": dev,
                                 "gross loss / mean exposure": gross / sum_mu if sum_mu else 0.0})
                    cx = [(paths[d.idx].comp_x, d.bond_unprov) for d in compromised]
                    comp.append(_comp_row("unprovisioned", wl, rule, adm, q, qh, cx, sum(d.mu for d in compromised)))
        for q in grid:
            ex = f0 * np.array([d.mu for d in draws])
            ts = [hold_time_threshold(_cust(d, d.bond_unprov), float(e), q) for d, e in zip(draws, ex)]
            tstar.append(_tstar_row("unprovisioned", wl, "-", q, ts, [d.hold for d in draws]))

        # ---- coalitions, at the reference workload only: every member sits at its own admission cap
        if int(wl) == ref:
            rng = np.random.default_rng([seed, 7, ref])
            c_cfg = P["coalition"]
            n_route, ext = int(c_cfg["route_length"]), float(c_cfg["external_detection"])
            for rule in ("oracle", "floor"):
                for q in grid:
                    qh = q_hat_for(rule, q, P)
                    for k in c_cfg["sizes"]:
                        k = int(k)
                        hits = 0
                        for _ in range(int(c_cfg["draws_per_cell"])):
                            idx = rng.choice(len(draws), n_route, replace=False)
                            ms = [_cust(draws[i], prov_bond(draws[i], qh)) for i in idx[:k]]
                            xs = [f0 * draws[i].mu for i in idx[:k]]
                            hits += coalition_rational(ms, xs, coalition_q(q, n_route, k, ext))
                        coal.append({"rule": rule, "q": q, "q_hat": qh, "coalition size": k,
                                     "draws": int(c_cfg["draws_per_cell"]), "rational": hits,
                                     "share rational": hits / int(c_cfg["draws_per_cell"])})

    return {"loss": pd.DataFrame(loss), "refusal": pd.DataFrame(refusal), "capacity": pd.DataFrame(cap_sens),
            "bond": pd.DataFrame(bonds), "tstar": pd.DataFrame(tstar), "compromised": pd.DataFrame(comp),
            "coalition": pd.DataFrame(coal)}


def _comp_row(pop, wl, rule, adm, q, qh, cx, sum_mu) -> dict:
    gross = sum(x for x, _ in cx)
    recovered = sum(q * min(x, b) for x, b in cx)  # the bond pays only if the theft is detected
    return {"population": pop, "workload": wl, "rule": rule, "admission": adm, "q": q, "q_hat": qh,
            "compromised custodians": len(cx), "deviating": len(cx), "gross loss / mean exposure":
            gross / sum_mu if sum_mu else 0.0, "expected uncovered / mean exposure":
            (gross - recovered) / sum_mu if sum_mu else 0.0}


def _tstar_row(pop, wl, rule, q, ts, holds) -> dict:
    finite = [t for t in ts if t is not None and not math.isinf(t)]
    return {"population": pop, "workload": wl, "rule": rule, "q": q,
            "share unbounded": float(np.mean([t is not None and math.isinf(t) for t in ts])),
            "share infeasible": float(np.mean([t is None for t in ts])),
            "median T* (days, finite)": float(np.median(finite)) if finite else float("nan"),
            "share with hold <= T*": float(np.mean([t is not None and h <= t + 1e-9 for t, h in zip(ts, holds)]))}


# ------------------------------------------------------------------ H6 and the PayeeBench A13 link

def decide_h6(P: dict, tabs: Dict[str, pd.DataFrame], threshold: float) -> dict:
    ref = int(P["workloads"]["reference"])
    L = tabs["loss"]
    a = L[(L.population == "provisioned") & (L.admission == "on") & L.rule.isin(["oracle", "floor"])]
    a_ok = bool((a.deviating == 0).all())
    R = tabs["refusal"]
    b = R[(R.population == "provisioned") & (R.workload == ref) & R.rule.isin(["oracle", "floor"])]
    worst = float(b["refusal rate"].max())
    b_ok = worst <= threshold
    opt = L[(L.population == "provisioned") & (L.admission == "on") & (L.rule == "optimistic")]
    return {"supported": a_ok and b_ok, "a_losses_zero": a_ok, "a_cells": int(len(a)),
            "a_max_deviating": int(a.deviating.max()), "b_refusal_ok": b_ok, "b_worst_refusal_rate": worst,
            "b_threshold": threshold, "reference_workload": ref,
            "optimistic_rule_deviating_total": int(opt.deviating.sum()),
            "kill_rule_triggered": not (a_ok and b_ok),
            "note": "q is swept, not measured; the kill rule also applies if q cannot be bounded credibly from below"}


def a13_bench(P: dict, seed: int) -> pd.DataFrame:
    """PayeeBench A13 cases (a custodian deviates after committing) generated
    from the rational-deviation condition: each case gets a custodian and an
    in-flight exposure at which stealing pays at the true q. M3 (v1 and v2
    mechanisms plus receipts and scheduling) does not stop them; M5 (M3 plus
    funded routes) refuses the payment when it would take the custodian past
    its cap."""
    from payeebench.runner import build_bench, run
    from .e2_e3 import calibrated_cba

    cfg = P["a13_bench"]
    n, q = int(cfg["cases"]), float(cfg["true_q"])
    qh = q_hat_for(cfg["rule"], q, P)
    mean_amt = mean_amount(P["payment_amount"], seed)
    world, cases = build_bench(seed=7, n_attack=n, n_benign=0, n_pv=0, attacks=("A13",), pvs=())
    recs = run(world, cases, ["M3"], delta=world.delta, cba_params=calibrated_cba(), seed=seed)
    m3 = {r["case_id"]: r for r in recs}
    rng = np.random.default_rng([seed, 13])
    draws = draw_custodians(P, 4 * n, int(P["workloads"]["reference"]), seed, mean_amt)
    rows = []
    for c in cases:
        d = draws[int(rng.integers(len(draws)))]
        cu = _cust(d, d.bond_unprov)
        x = deviation_threshold(cu, q) * (1.0 + 1e-6 + float(rng.exponential(0.5)))  # exposure at which stealing pays
        x = max(x, float(c.payment.amount))
        assert rational_to_deviate(cu, x, q)
        refused_m5 = x > admission_cap(cu, qh)
        r = m3[c.case_id]
        rows.append({"case_id": c.case_id, "variant": c.variant, "rail": c.rail, "custodian bond / mean exposure":
                     d.bond_unprov / d.mu, "exposure / mean exposure": x / d.mu, "M3 loss": bool(r["loss"]),
                     "M3 breach certificate": bool(r["breach_certificate"]), "M5 refused": bool(refused_m5),
                     "M5 loss": bool(r["loss"]) and not refused_m5})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ outputs

def _pivot(df: pd.DataFrame, rows: List[str], value) -> pd.DataFrame:
    return df.pivot_table(index=rows, columns="q", values=value, aggfunc="first")


def run_e11(dry_run_dir: Optional[str] = None) -> dict:
    """Run E11 and write the tables. Refuses unless hypotheses_v2.yaml is
    locked and consistent with the v1 lock."""
    st = prereg.v2_status()
    if not st["ok"]:
        raise RuntimeError(f"E11 refused: {st['reason']}")
    spec = prereg.load_v2()
    P = copy.deepcopy(spec["experiment"])
    seed = int(spec["seeds"]["e11"])
    if QUICK:  # smoke run only; not evidence
        P["custodians_per_cell"] = min(P["custodians_per_cell"], 20)
        P["coalition"]["draws_per_cell"] = 200
        P["bootstrap"]["resamples"] = 200
    with Timer("E11 funded-route population simulation"):
        tabs = simulate(P, seed)
    threshold = float(spec["hypotheses"]["H6"]["target"]["refusal_rate_legitimate_payments"]["max"])
    h6 = decide_h6(P, tabs, threshold)
    with Timer("E11 PayeeBench A13 cases"):
        bench = a13_bench(P, seed)
    for name, df in {**tabs, "a13_bench": bench}.items():
        write_csv(f"e11_{name}", df)

    L, R = tabs["loss"], tabs["refusal"]
    ref = int(P["workloads"]["reference"])
    note_q = ("q is an input, swept from 0.3 to 1, not a measurement. Simulation of an economic model; the "
              "numbers say nothing about any deployed custodian.")

    lp = L[(L.workload == ref)].copy()
    lp["deviating / rational"] = lp.deviating.astype(str) + "/" + lp["rational custodians"].astype(str)
    write_table("e11_loss", _pivot(lp, ["population", "rule", "admission"], "deviating / rational"),
                f"E11: rational custodians that steal, reference workload ({ref} payments in flight)",
                "Exact counts over simulated custodians. Provisioned: bond sized so the cap is "
                f"{P['capacity_factor']} x mean exposure at the rule's q_hat. " + note_q)
    rp = R[(R.workload == ref)].copy()
    rp["refusal"] = rp["refusal rate"].map(lambda v: f"{v:.4f}")
    write_table("e11_refusal", _pivot(rp, ["population", "rule"], "refusal"),
                f"E11: refusal rate on legitimate payments, reference workload ({ref} payments in flight)",
                f"Pooled over custodians; cluster bootstrap by custodian in e11_refusal.csv. Target at most "
                f"{threshold}. For the provisioned population the cap is the same at every q, so the refusal "
                "rate does not depend on q; what q changes is the bond required (e11_bond). " + note_q)
    cs = tabs["capacity"].copy()
    write_table("e11_capacity", cs.round(4), "E11: refusal rate against capacity provisioning (not part of the H6 decision)",
                index=False)
    wl_tab = R[(R.population == "provisioned") & (R.rule == "oracle") & (R.q == P["detection_grid"][0])][
        ["workload", "payments", "refused", "refusal rate", "bootstrap lo", "bootstrap hi"]]
    write_table("e11_refusal_by_workload", wl_tab.round(4), "E11: refusal rate by mean payments in flight "
                "(provisioned, capacity factor " + str(P["capacity_factor"]) + ")", index=False)
    bt = tabs["bond"][tabs["bond"].workload == ref].drop(columns="workload")
    write_table("e11_bond", bt.round(3), f"E11: bond required per unit of mean exposure to sustain the capacity, by assumed q_hat",
                "A smaller q_hat means a larger bond. 'Deterrence binds' means the bond must exceed the capacity "
                "itself, because the custodian's franchise and the discounted bond do not deter at that q_hat.",
                index=False)
    ts = tabs["tstar"][tabs["tstar"].workload == ref]
    write_table("e11_tstar", ts.drop(columns="workload").round(3),
                f"E11: hold-time threshold T* at exposure = {P['capacity_factor']} x mean (days)",
                "unbounded: margin and franchise alone deter; infeasible: even immediate release is not enough "
                "for this bond. Provisioned rows use the bond for the named rule.", index=False)
    cp = tabs["compromised"][tabs["compromised"].workload == ref]
    write_table("e11_compromised", cp.round(4).drop(columns="workload"),
                "E11: compromised custodians (deviate at a random time whatever the incentives)",
                "The rule cannot deter them; the bond gives coverage only if the theft is detected "
                "(expected uncovered loss = gross - q x min(exposure, bond)). Reported apart from the rational "
                "custodians.", index=False)
    cl = tabs["coalition"].copy()
    cl["share rational"] = cl["share rational"].map(lambda v: f"{v:.3f}")
    write_table("e11_coalition", _pivot(cl, ["rule", "coalition size"], "share rational"),
                "E11: share of coalitions for which joint deviation pays, every member at its admission cap",
                "Route of 3 custodians; colluders withhold their own evidence, so detection falls to the remaining "
                "honest hops and a 0.1 external channel (see hypotheses_v2.yaml).")
    n_b = len(bench)
    bsum = pd.DataFrame([{"configuration": "M3", "losses": f"{int(bench['M3 loss'].sum())}/{n_b}",
                          "with breach certificate": f"{int((bench['M3 loss'] & bench['M3 breach certificate']).sum())}/"
                                                     f"{int(bench['M3 loss'].sum())}", "refused": "0/%d" % n_b},
                         {"configuration": "M5 (M3 + F6)", "losses": f"{int(bench['M5 loss'].sum())}/{n_b}",
                          "with breach certificate": "-", "refused": f"{int(bench['M5 refused'].sum())}/{n_b}"}])
    write_table("e11_a13_bench", bsum, "E11: PayeeBench A13 cases generated from the rational-deviation condition",
                f"Each case gets a custodian and an exposure at which stealing pays at q = {P['a13_bench']['true_q']}; "
                "M5 refuses the payment when the exposure exceeds the cap. M5's refusals of legitimate payments are "
                "in e11_refusal. " + note_q, index=False)
    summary = {"H6": h6, "mean_amount_cents": mean_amount(P["payment_amount"], seed), "seed": seed,
               "preregistration_v2_sha256": st["v2_sha256"], "quick": QUICK,
               "a13_bench": {"M3_losses": int(bench["M3 loss"].sum()), "M5_losses": int(bench["M5 loss"].sum()),
                             "M5_refused": int(bench["M5 refused"].sum()), "cases": n_b}}
    write_json("e11_summary", summary)
    return summary


if __name__ == "__main__":
    print(run_e11())
