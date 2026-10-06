"""E4 anchoring calibration (CBA).

Genuine brands are drawn from the Tranco top list (ID recorded in
data/upstream/PINS.txt); lookalikes are generated with dnstwist-style
techniques. Logos are synthetic wordmarks (cloned logos are re-encoded
copies), descriptions are copied for cloned sites. The calibration split
fixes (theta, tau); the held-out split reports the operating point.

Outputs: ROC of lookalike detection per confusability component, step-up
vs false-commit trade-off, component ablation, prevalence sensitivity, and
results/raw/cba_calibration.json used by E2.
"""

from __future__ import annotations

import os
import random
from dataclasses import replace
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from meridian.cba import CBA, Candidate, CBAParams, Registry, phash, render_logo
from meridian.core.ids import make_lei
from payeebench.names import TECHNIQUES, lookalike
from payeebench.runner import shared_embedder

from .common import FIGURES, QUICK, RAW, ROOT, SEED, Timer, write_csv, write_json, write_table
from .stats import fmt_rate

TRANCO = os.path.join(ROOT, "data", "tranco", "tranco_56WKN_top20k.csv")  # Tranco list 56WKN, top 20k
OK_TLDS = {"com", "net", "org", "co.uk", "de", "fr", "in", "co.in", "nl", "es", "it", "shop", "store", "io"}


def tranco_brands(n: int, rng: random.Random) -> List[Tuple[str, str]]:
    with open(TRANCO, encoding="utf-8") as fh:
        raw = fh.read().splitlines()
    out, seen = [], set()
    for line in raw[:20000]:
        _, dom = line.split(",", 1)
        parts = dom.split(".")
        tld = ".".join(parts[1:])
        label = parts[0]
        if tld not in OK_TLDS or not label.isalpha() or not 4 <= len(label) <= 12 or label in seen:
            continue
        seen.add(label)
        out.append((label.capitalize(), dom))
    rng.shuffle(out)
    return out[:n]


def build(n_brands: int, prevalence: float, rng: random.Random, group_share: float = 0.1):
    brands = tranco_brands(n_brands, rng)
    genuine: List[Candidate] = []
    looks: Dict[str, List[Candidate]] = {}
    for i, (name, dom) in enumerate(brands):
        color = tuple(rng.randrange(30, 220) for _ in range(3))
        lei = make_lei(f"e4|{dom}")
        c = Candidate(f"brand:{dom}", name, dom, lei, phash(render_logo(name, color)), f"{name} official website",
                      first_seen=0, jurisdiction=rng.choice(["US", "GB", "DE", "IN"]))
        genuine.append(c)
        if rng.random() < group_share:
            # the same brand on a regional domain of the same legal entity:
            # identical name, same LEI, so it must not count as a rival
            label = dom.split(".")[0]
            sib_dom = f"{label}.{rng.choice(['co.uk', 'de', 'fr', 'in', 'es'])}"
            if sib_dom != dom:
                genuine.append(Candidate(f"brand:{sib_dom}", name, sib_dom, lei, c.logo_hash,
                                         f"{name} official website", 0, c.jurisdiction))
        if rng.random() < prevalence:
            looks[c.brand_id] = []
            for k in range(rng.choice([1, 1, 2, 3])):
                tech = rng.choice(TECHNIQUES)
                disp, ldom = lookalike(name, dom, tech, rng)
                if ldom == dom:
                    continue
                cloned = rng.random() < 0.7
                logo = phash(render_logo(name, color, seed=rng.randrange(10**6), jitter=0.4)) if cloned else \
                    phash(render_logo(disp, tuple(rng.randrange(30, 220) for _ in range(3))))
                looks[c.brand_id].append(Candidate(
                    f"brand:{ldom}", disp, ldom, make_lei(f"e4-look|{ldom}|{k}"), logo,
                    f"{name} official website" if cloned else f"{disp} store", 10, rng.choice(["US", "GB", "SG"])))
                looks[c.brand_id][-1].__dict__["technique"] = tech
    return genuine, looks


def user_words(c: Candidate, rng: random.Random) -> str:
    r = rng.random()
    w = c.name
    if r < 0.05 and len(w) > 4:
        i = rng.randrange(1, len(w) - 1)
        return w[:i] + w[i + 1:]
    if r < 0.35:
        return w.lower()
    return w


def evaluate(cba: CBA, genuine: List[Candidate], looks: Dict[str, List[Candidate]], ids: set,
             rng_seed: int) -> Dict[str, float]:
    rng = random.Random(rng_seed)
    ben_step = ben_wrong = ben_n = 0
    att_fc = att_step = att_n = 0
    for c in genuine:
        if c.brand_id not in ids:
            continue
        w = user_words(c, rng)
        r = cba.anchor(w, [c])
        ben_n += 1
        if not r.committed:
            ben_step += 1
        elif cba.registry.by_id[r.brand].lei != c.lei:
            # committing to the same legal entity's other domain is not an error
            ben_wrong += 1
        for lk in looks.get(c.brand_id, []):
            r = cba.anchor(w, [lk])
            att_n += 1
            if r.committed and cba.registry.by_id[r.brand].lei != c.lei:
                att_fc += 1
            elif not r.committed:
                att_step += 1
    return {"benign_step_up": ben_step / max(1, ben_n), "benign_wrong_commit": ben_wrong / max(1, ben_n),
            "attack_false_commit": att_fc / max(1, att_n), "attack_step_up": att_step / max(1, att_n),
            "benign_n": ben_n, "attack_n": att_n, "benign_step_k": ben_step, "attack_fc_k": att_fc}


def auc(pos: List[float], neg: List[float]) -> float:
    if not pos or not neg:
        return float("nan")
    u = mannwhitneyu(pos, neg, alternative="greater").statistic
    return float(u / (len(pos) * len(neg)))


def run_e4() -> dict:
    rng = random.Random(SEED)
    n = 300 if QUICK else 1200
    emb = shared_embedder()
    with Timer(f"E4 build {n} Tranco brands with lookalikes"):
        genuine, looks = build(n, prevalence=0.3, rng=rng)
        reg = Registry(genuine + [l for ls in looks.values() for l in ls])
        emb.encode([c.description for c in reg.by_id.values()] + [c.name for c in reg.by_id.values()])
    ids = sorted({c.brand_id for c in genuine})
    random.Random(SEED + 4).shuffle(ids)
    calib, test = set(ids[: len(ids) // 2]), set(ids[len(ids) // 2:])

    # lookalike detection ROC per component
    base = CBA(reg, CBAParams(), emb)
    others = [c for c in genuine]
    pos: Dict[str, List[float]] = {k: [] for k in ("str", "vis", "sem", "kappa")}
    neg: Dict[str, List[float]] = {k: [] for k in ("str", "vis", "sem", "kappa")}
    by_tech: Dict[str, List[float]] = {}
    prng = random.Random(SEED + 5)
    for c in genuine:
        for lk in looks.get(c.brand_id, []):
            parts = base.kappa_parts(c, lk)
            for k, v in parts.items():
                pos[k].append(v)
            kap = base.kappa(c, lk)
            pos["kappa"].append(kap)
            by_tech.setdefault(lk.__dict__.get("technique", "?"), []).append(kap)
        o = prng.choice(others)
        if o.lei != c.lei:
            parts = base.kappa_parts(c, o)
            for k, v in parts.items():
                neg[k].append(v)
            neg["kappa"].append(base.kappa(c, o))
    roc_rows = [{"score": k, "AUC lookalike vs unrelated": round(auc(pos[k], neg[k]), 4), "n_pos": len(pos[k]),
                 "n_neg": len(neg[k])} for k in pos]
    write_table("e4_detection_auc", pd.DataFrame(roc_rows), "E4: lookalike detection AUC by confusability component",
                index=False)
    tech_rows = [{"technique": t, "n": len(v), "median kappa": round(float(np.median(v)), 3),
                  "share kappa >= 0.6": round(float(np.mean(np.array(v) >= 0.6)), 3)} for t, v in sorted(by_tech.items())]
    write_table("e4_by_technique", pd.DataFrame(tech_rows), "E4: confusability by lookalike technique", index=False)

    # operating curve on the calibration split
    curve = []
    taus = [0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.125, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
    thetas = [0.5, 0.6, 0.7, 0.8] if QUICK else [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    with Timer("E4 sweep theta x tau on the calibration split"):
        for th in thetas:
            for tau in taus:
                cba = CBA(reg, CBAParams(theta=th, tau=float(tau)), emb)
                r = evaluate(cba, genuine, looks, calib, SEED)
                curve.append({"theta": th, "tau": float(tau), **r})
    cv = pd.DataFrame(curve)
    write_csv("e4_curve_calibration", cv)
    # selection rule: lowest benign step-up among points that commit to a
    # lookalike at most 1% of the time and never mis-anchor more than 0.5% of
    # benign requests; ties go to the larger margin
    safe = cv[(cv.attack_false_commit <= 0.01) & (cv.benign_wrong_commit <= 0.005)]
    if len(safe):
        pick = safe.sort_values(["benign_step_up", "attack_false_commit", "tau"],
                                ascending=[True, True, False]).iloc[0]
    else:  # no safe point: minimise mis-anchoring first, never trade it for fewer step-ups
        cv["_err"] = cv.attack_false_commit + cv.benign_wrong_commit
        pick = cv.sort_values(["_err", "benign_step_up", "tau"], ascending=[True, True, False]).iloc[0]
    params = CBAParams(theta=float(pick.theta), tau=float(pick.tau))

    # held-out evaluation and ablations
    rows = []
    for name, use in [("all (str+vis+sem)", ("str", "vis", "sem")), ("string only", ("str",)), ("visual only", ("vis",)),
                      ("semantic only", ("sem",)), ("string+visual", ("str", "vis")), ("string+semantic", ("str", "sem"))]:
        cba = CBA(reg, replace(params, use=use), emb)
        r = evaluate(cba, genuine, looks, test, SEED + 1)
        rows.append({"components": name, "benign step-up": fmt_rate(r["benign_step_k"], r["benign_n"]),
                     "benign wrong commit": round(r["benign_wrong_commit"], 4),
                     "attack false commit": fmt_rate(r["attack_fc_k"], r["attack_n"]),
                     "attack step-up": round(r["attack_step_up"], 4)})
    # no LEI distinction: same-group brands become rivals
    class NoLEI(CBA):
        def kappa(self, x, y):
            p = self.params
            from meridian.cba.features import noisy_or
            return noisy_or(self.kappa_parts(x, y), {"str": p.w_str, "vis": p.w_vis, "sem": p.w_sem})
    r = evaluate(NoLEI(reg, params, emb), genuine, looks, test, SEED + 1)
    rows.append({"components": "all, without LEI distinction", "benign step-up": fmt_rate(r["benign_step_k"], r["benign_n"]),
                 "benign wrong commit": round(r["benign_wrong_commit"], 4),
                 "attack false commit": fmt_rate(r["attack_fc_k"], r["attack_n"]),
                 "attack step-up": round(r["attack_step_up"], 4)})
    write_table("e4_ablation_heldout", pd.DataFrame(rows),
                f"E4: held-out operating point (theta={params.theta}, tau={params.tau}) and component ablation",
                "Wilson 95% intervals. Prevalence of impersonated brands in the registry: 30%.", index=False)

    # prevalence sensitivity at the chosen point
    prev_rows = []
    for prev in [0.05, 0.2, 0.5, 1.0]:
        g2, l2 = build(n // 2, prevalence=prev, rng=random.Random(SEED + int(prev * 100)))
        reg2 = Registry(g2 + [l for ls in l2.values() for l in ls])
        r = evaluate(CBA(reg2, params, emb), g2, l2, {c.brand_id for c in g2}, SEED + 2)
        prev_rows.append({"impersonated share": prev, "benign step-up": fmt_rate(r["benign_step_k"], r["benign_n"]),
                          "attack false commit": fmt_rate(r["attack_fc_k"], r["attack_n"])})
    write_table("e4_prevalence", pd.DataFrame(prev_rows), "E4: sensitivity to the share of brands with lookalikes",
                index=False)

    cal = {"theta": params.theta, "tau": params.tau, "w_str": params.w_str, "w_vis": params.w_vis,
           "w_sem": params.w_sem, "s_min": params.s_min, "embedding_backend": emb.backend,
           "calibration_point": pick.to_dict()}
    write_json("cba_calibration", cal)
    return cal


if __name__ == "__main__":
    print(run_e4())
