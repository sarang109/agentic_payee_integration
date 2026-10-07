"""Assemble results/REPORT.md from the generated tables and summaries.

Every number in the report comes from a file under results/; the text only
says where to look, what each table measures and what kind of evidence it is.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

import pandas as pd

from .common import RAW, RESULTS, TABLES

# evidence labels (claims discipline): every section says what kind of
# evidence it contains
PROOF, MECH, CONSTRUCTED, SANDBOX, MODELLED, MEASURED, HOSTED = (
    "proof (docs/supplement/proofs.md)", "mechanized (Tamarin / ProVerif)",
    "exact counts over constructed cases", "measured on a sandbox or public testnet",
    "simulation over modelled timings (config/rails.yaml)", "measured (timing or passive web measurement)",
    "measured with a hosted model")

# (title, tables, figure, note, evidence, paper)
SECTIONS = [
    ("Mechanized verification", ["formal_results"], None,
     "Tamarin models of the RAP exchange (T1, T2, T4), committed routes and attributability (T10, T11), and the "
     "AP2/ACP-style checkout with and without the extension (P10, P18); ProVerif equivalence for the private lookup.",
     [MECH], "1 (Tamarin), 2 (ProVerif)"),
    ("F3 toy check, T4 mutation tests, F5 split hardness", ["f3_toy", "t4_mutations", "f5_split"], None, "",
     [CONSTRUCTED], "1"),
    ("E1 V1a directory vs V1b proof-carrying", ["e1_latency", "e1_disagreements", "e1_outage_lying", "e1_leakage"],
     None, "", [CONSTRUCTED, MEASURED + " for latency"], "1"),
    ("E2 attack matrix", ["e2_attack_matrix_loss", "e2_attack_matrix_stepup", "e2_by_variant", "e2_premise_violation",
                          "e2_mcnemar"], "e2_attack_heatmap.png", "", [CONSTRUCTED], "1"),
    ("E2 external scenarios (AIP-Bench)", ["e2_aip_external"], None, "", [CONSTRUCTED, "exploratory"], "1"),
    ("E3 legitimate structures", ["e3_cost_vs_benefit", "e3_false_block", "e3_step_up", "e3_stepup_causes", "e3_stepup_exposure",
                                  "e3_rates_bootstrap"], None, "", [CONSTRUCTED], "1"),
    ("RQ5 per-rail comparison", ["rq5_per_rail", "rq5_pareto", "rq5_bnpl_supplement", "rq5_pareto_with_bnpl"], None,
     "", [CONSTRUCTED, "rq5_pareto and the BNPL supplement are exploratory"], "2"),
    ("E4 anchoring calibration", ["e4_detection_auc", "e4_by_technique", "e4_ablation_heldout", "e4_string_weak",
                                  "e4_prevalence"], "e4_cba_tradeoff.png", "",
     [CONSTRUCTED, "e4_string_weak is exploratory"], "1"),
    ("E4b anchoring against real phishing domains (UCI PhiUSIIL)", ["e4b_phishing", "e4b_by_match", "e4b_coverage"],
     None, "", ["real dataset, Wilson intervals"], "1"),
    ("E4c anchoring on Kaggle phishing and homograph datasets", ["e4c_homograph", "e4c_url_datasets", "e4c_coverage",
                                                                 "e4c_by_match", "e4c_files"], None,
     "Runs with a Kaggle API token; the files used are listed with their SHA-256.", ["real datasets"], "1"),
    ("E5 probation sweep", ["e5_probation", "e5_monitor_reaction", "e5_cap"], "e5_probation.png", "",
     [CONSTRUCTED], "1"),
    ("E6 rail scheduling", ["e6_timing_sources", "e6_residual_loss_f0", "e6_observer_corruption", "e6_rws_choice",
                            "e6_theorem3", "f4_toy"], "e6_rail_residual.png", "", [MODELLED,
                                                                                   "card void latency " + SANDBOX], "2"),
    ("Gate A2: baseline B2 against upstream AP2 code", ["upstream_b2_agreement", "upstream_empty_id_wildcard"], None,
     "Runs the AP2 SDK payee check at the pinned commit (fetched into data/upstream/src, git-ignored); skipped "
     "without network. B5 has no reference implementation and stays re-specified.",
     [MEASURED + " by running upstream code on constructed cases"], "1"),
    ("E12 author-written attacks (Gate A; not independent)", ["e12_attack_matrix", "e12_mcnemar", "e12_by_scenario",
                                                       "e12_by_author"], None,
     "The attack set was written from the schema in docs/e12/AUTHORING.md by the same side that built the "
     "generator, with the generator in view, so it is author-dependent and does not answer the circular-evaluation "
     "objection (e12/ERRATA.md). It was validated against ground truth only and frozen (e12/LOCK) with the "
     "decision rule (e12/DECISION_RULE.md) before this run. The attacks are compiled onto the same world builder "
     "as the main benchmark. The two author labels are batches, not independent people.",
     [CONSTRUCTED], "1"),
    ("E11 funded routes (F6), hypothesis H6", ["e11_loss", "e11_refusal", "e11_refusal_by_workload", "e11_capacity",
                                                "e11_bond", "e11_tstar", "e11_compromised", "e11_coalition",
                                                "e11_a13_bench"], None,
     "Registered in preregistration/hypotheses_v2.yaml and locked in LOCK_V2 before the run. The detection "
     "probability q is swept, not measured.", [MODELLED + "; no custodian or detection process is measured"], "2"),
    ("X2 / X3 on Stripe Connect test mode", ["stripe_connect"], None,
     "Runs only with a Stripe test key on an account with Connect enabled; otherwise the table records why it was "
     "skipped.", [SANDBOX], "1"),
    ("x402 on a public testnet", ["x402_testnet"], None, "", [SANDBOX], "2"),
    ("E7 privacy cost (V4) and H4", ["e7_latency", "e7_sizes", "e7_lookups", "e7_h4_disagreements", "e7_leakage"], None,
     "", [MEASURED + " for proof cost", CONSTRUCTED + " for H4 agreement"], "2"),
    ("E8 scalability", ["e8_pav", "e8_directory", "e8_log"], None, "", [MEASURED + " on synthetic graphs"], "1"),
    ("E9 agent containment", ["e9_hosted_injected", "e9_hosted_benign", "e9_hosted_cost", "e9_agentdojo",
                              "e9_agentdojo_benign", "e9_synthetic_benign", "e9_compromise_vs_payment",
                              "e9_marketplace"], None,
     "The e9_hosted_* tables use a hosted model as the agent; the others use scripted worst-case agents.",
     [HOSTED, CONSTRUCTED + " for scripted agents"], "2"),
    ("E10 coverage in the wild", ["e10_coverage", "e10b_coverage", "e10_lookalike_prevalence"], None, "",
     [MEASURED + "; reruns query live DNS, TLS and GLEIF and give different numbers"], "1"),
    ("Ablations", ["ablation1_bilateral", "ablation2_scope_meet", "ablation3_rho"], None,
     "Ablation 4 (probation) is E5, 5 (observers and collusion) is E6, 6 (RAP vs directory) is E1.",
     [CONSTRUCTED], "1 (ablations 1-4, 6), 2 (ablation 5)"),
]


def _load(name: str, folder: str = RAW) -> Optional[dict]:
    p = os.path.join(folder, f"{name}.json")
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


def _csv(name: str) -> Optional[pd.DataFrame]:
    p = os.path.join(TABLES, f"{name}.csv")
    return pd.read_csv(p) if os.path.exists(p) else None


def _table(name: str) -> str:
    p = os.path.join(TABLES, f"{name}.md")
    if not os.path.exists(p):
        return f"_({name} not produced in this run)_\n"
    with open(p) as fh:
        return fh.read().replace("### ", "#### ", 1)


def _verdict(v) -> str:
    if v is None:
        return "not evaluated"
    return "supported" if v else "not supported"


def _frac(s: str) -> tuple:
    try:
        a, b = str(s).split()[0].split("/")
        return int(a), int(b)
    except Exception:
        return None, None


def limitations(e6: dict, e23: dict, e7: dict, e9: dict) -> List[str]:
    """Limitations computed from the tables of this run."""
    out = []
    oc = _csv("e6_observer_corruption")
    if oc is not None:
        oc.columns = [str(c) for c in oc.columns]
        cust = oc[(oc.rail == "card") & (oc.scenario == "custodian")]
        if len(cust):
            worst = cust[["0", "1", "2"]].min().min()
            out.append(f"Custodian deviation on the card rail is not undone by any mode: residual loss is at least "
                       f"{worst:.3g} for every f in {{0, 1, 2}} (e6_observer_corruption). The deviation happens after "
                       f"capture, outside the window; only the breach certificate (Theorem 2) remains.")
        fh = oc[(oc.rail == "card") & (oc.scenario == "first-hop") & (oc["mode"] == "RWS")]
        if len(fh):
            r = fh.iloc[0]
            out.append(f"RWS on the card first hop holds while honest observers remain (residual loss {r['0']:g} at "
                       f"f = 0, {r['1']:g} at f = 1) and fails once both G1 observers are corrupted "
                       f"({r['2']:g} at f = 2).")
    m = _csv("e2_attack_matrix_loss")
    if m is not None:
        row = m[m.iloc[:, 0].astype(str).str.startswith("A13")]
        if len(row):
            r = row.iloc[0]
            cert = ""
            rp = os.path.join(RAW, "payeebench_records.csv")
            if os.path.exists(rp):
                d = pd.read_csv(rp, usecols=["kind", "config", "loss", "breach_certificate"])
                x = d[(d.kind == "A13") & (d.config == "M3") & d.loss]
                cert = f"; {int(x.breach_certificate.sum())} of the {len(x)} M3 losses carry a breach certificate"
            out.append(f"A13 (a custodian deviates after committing) is not prevented: M2 {r.get('M2')}, M3 "
                       f"{r.get('M3')} losses{cert} (Theorem 2: attributable, not prevented).")
    bn = _csv("rq5_bnpl_supplement")
    if bn is not None:
        out.append("On the BNPL route (exploratory supplement), M3 does not undo first-hop or custodian diversions: "
                   "the modelled BNPL void success (0.98) is below 1 - eps, so POST is not POST-safe and RWS falls "
                   "back to PRE. The strongest baseline B7 stops some of these through the receipt service's view.")
    h4 = e7.get("H4", {})
    if h4.get("bbs_verify_p95_ms") is not None and not h4.get("bbs_meets_latency_target", True):
        out.append(f"H4 holds for the SNARK variant only; the BBS variant's payer-side verify p95 is "
                   f"{h4['bbs_verify_p95_ms']:.0f} ms, above the 150 ms target.")
    hm = e9.get("hosted_models")
    if hm:
        models = [hm] if isinstance(hm, str) else list(hm)
        if len(models) == 1:
            out.append(f"Hosted-model evidence (E9) covers a single model ({models[0]}); results may not carry over "
                       f"to other models, and no second model was run.")
    out.append("V4 hides acquiring relationships and the terminal account but not the brand or payee identifier; "
               "proofs for one merchant are linkable, and the k-anonymous lookup's anonymity set shrinks with the "
               "prefix length and log size (e7_leakage, e7_lookups).")
    out.append("Rail windows, observer latencies and every void or recall latency except the card void are modelled "
               "(config/rails.yaml); see e6_timing_sources. Issuer authorization records (ISO 8583 fields) are "
               "simulated; no real issuer data was available.")
    out.append("PayeeBench attacks, legitimate structures and the strongest baseline B7 are built from the same "
               "generator and grammar, so 0% false block on those structures is partly by construction. The "
               "AIP-Bench scenarios fix the attack externally but are instantiated by the same generator.")
    if e9.get("hosted"):
        out.append("In the hosted-model runs an allowlist of past counterparties also stops every novel-payee "
                   "diversion; MERIDIAN's measured advantage over it is fewer step-ups on legitimate new payees, "
                   "not lower loss (e9_hosted_injected, e9_hosted_benign).")
    return out


def build_report() -> str:
    status = _load("run_status", RESULTS) or {}
    e23 = _load("e2_e3_summary") or {}
    e6 = _load("e6_summary") or {}
    e7 = _load("e7_summary") or {}
    e9 = _load("e9_summary") or {}
    e10 = _load("e10_summary") or {}
    formal = _load("formal_summary") or {}
    toys = _load("toys_summary") or {}
    e1 = _load("e1_summary") or {}
    e4b = _load("e4b_summary") or {}
    e4c = _load("e4c_summary") or {}
    cal = _load("cba_calibration") or {}
    xmeta = _load("x402_testnet_meta") or {}
    env = status.get("environment", {})
    lines = ["# MERIDIAN results", ""]
    lines += [f"Generated {env.get('time_utc', '?')} from commit `{env.get('git', '?')}`, seed {env.get('seed', '?')}"
              f"{' (quick mode)' if env.get('quick') else ''}. Pre-registration SHA-256 "
              f"`{status.get('preregistration_sha256', '?')}` "
              f"({'matches the lock' if status.get('preregistration_locked') else 'DOES NOT match the lock'}).", ""]
    lines += ["## Run status", "", "| step | status | seconds |", "|---|---|---|"]
    for s, v in status.get("steps", {}).items():
        lines.append(f"| {s} | {v['status']} | {v.get('seconds', '')} |")
    lines += [""]

    lines += ["## Hypotheses (decision rules fixed in preregistration/hypotheses.yaml)", "",
              "| hypothesis | paper | verdict | evidence |", "|---|---|---|---|"]
    h1, h2, h5 = e23.get("H1", {}), e23.get("H2", {}), e23.get("H5", {})
    lines.append(f"| H1 V1 admits no out-of-closure payee; baselines do; false blocks <= 1% | 1 | "
                 f"{_verdict(h1.get('supported'))} | M1 loss on A3/A4/A5/A7/A8: {h1.get('m1_loss_on_v1_classes')}; "
                 f"baselines: {h1.get('baseline_losses_on_v1_classes')}; M1 false-block rate {h1.get('m1_false_block_rate')} |")
    e4_step, e4_prev = None, []
    ab = _csv("e4_ablation_heldout")
    if ab is not None:
        comp = "string only" if list(cal.get("use", [])) == ["str"] else "all (str+vis+sem)"
        e4_step = ab[ab.components == comp]["benign step-up"].iloc[0]
    pv = _csv("e4_prevalence")
    if pv is not None:
        e4_prev = [f"{r['impersonated share']:g} -> {str(r['benign step-up']).split()[0]}" for _, r in pv.iterrows()]
    m2l, m1l = h2.get("m2_loss_A1_A2", "?/?"), h2.get("m1_loss_A1_A2", "?/?")
    try:
        sec_ok = int(m2l.split("/")[0]) < int(m1l.split("/")[0]) and h2.get("mcnemar_p", 1) < 0.05
    except ValueError:
        sec_ok = False
    step_ok = e4_step is not None and float(str(e4_step).split()[0]) <= 0.05
    h2_verdict = "supported" if sec_ok and step_ok else (
        "partly supported: security part yes, step-up target not met" if sec_ok else "not supported")
    lines.append(f"| H2 V2 lowers lookalike success; benign step-up <= 5% (E4) | 1 | {h2_verdict} | A1-A2 loss M2 "
                 f"{m2l} vs M1 {m1l} (McNemar p = {h2.get('mcnemar_p', float('nan')):.2g}); E4 held-out benign "
                 f"step-up {e4_step} (CBA components: {'+'.join(cal.get('use', ['str', 'vis', 'sem']))}) with 30% of "
                 f"brands impersonated; by impersonated share: {'; '.join(e4_prev)}. "
                 f"Attack-dense bench: {h2.get('benign_cba_step_up')}. Real data (E4b, PhiUSIIL): benign step-up "
                 f"{(e4b.get('benign') or {}).get('stepped up')}, real phishing domains committed "
                 f"{(e4b.get('attack') or {}).get('committed to phishing domain')}; Kaggle homograph spoofs committed "
                 f"{(e4c.get('homograph_all') or {}).get('committed to spoof')} |")
    h3 = e6.get("H3", {})
    card_ci = ""
    try:
        from .stats import wilson
        k, n = (int(x) for x in h3.get("card_first_hop_POST_undone", "0/0").split("/"))
        lo, hi = wilson(k, n)
        card_ci = f" = {k / n:.4f}, 95% CI [{lo:.3f}, {hi:.3f}] against the 0.99 threshold"
    except Exception:
        pass
    void = e6.get("void") or {}
    sens = h3.get("card_first_hop_POST_undone_with_modelled_void")
    tail = (f"; card void latency from {void.get('backend')} (p50 {void.get('void_p50_s', 0):.2f} s, "
            f"success {void.get('void_success')})")
    sk, sn = _frac(sens) if sens else (None, None)
    if sk is not None and sn:
        tail += (f". Sensitivity: with the modelled void latency and success from config/rails.yaml instead, the "
                 f"same runs give {sens}, which {'also meets' if sk / sn >= 0.99 else 'misses'} the 0.99 threshold")
    lines.append(f"| H3 card POST detection when POST-safe holds; instant rails need PRE or escrow | 2 | "
                 f"{_verdict(h3.get('supported'))} | card: POST-safe probability {h3.get('card_post_safe_probability')}, "
                 f"first-hop swaps voided before capture {h3.get('card_first_hop_POST_undone')}{card_ci}; instant and "
                 f"stablecoin late evidence: POST undone {h3.get('instant_late_evidence_POST_undone')}, ESCROW undone "
                 f"{h3.get('instant_late_evidence_ESCROW_undone')}{tail} |")
    h4 = e7.get("H4", {})
    bbs = h4.get("bbs_verify_p95_ms")
    lines.append(f"| H4 V4 keeps decisions; payer p95 <= 150 ms | 2 | {_verdict(h4.get('supported'))} for the SNARK "
                 f"variant | agreement {h4.get('exact_verdict_agreement')} on {h4.get('cases')} cases; SNARK payer-side "
                 f"p95 {h4.get('added_payer_p95_ms') and round(h4.get('added_payer_p95_ms'), 1)} ms; prover p95 "
                 f"{h4.get('prover_p95_ms') and round(h4.get('prover_p95_ms'))} ms. The BBS variant was not part of "
                 f"the agreement test; its payer-side verify p95 is {bbs and round(bbs)} ms, "
                 f"{'within' if h4.get('bbs_meets_latency_target') else 'above'} the 150 ms target |")
    ex5 = e23.get("H5_exploratory_with_bnpl_supplement", {})
    lines.append(f"| H5 no single version dominates every rail | 2 | {_verdict(h5.get('supported'))} | lowest "
                 f"(loss, step-up) per rail, ties kept: {h5.get('best_meridian_configs_per_rail')}; among the best on "
                 f"every rail with attack data: {h5.get('best_on_every_rail')}; rails without attack cases: "
                 f"{h5.get('rails_without_attack_cases')}. An earlier computation broke ties by decision latency and "
                 f"counted the BNPL rail, which has no attack cases, and reported 'supported' "
                 f"({h5.get('legacy_latency_tiebreak')}); that verdict rested on the 0/0 cell and is withdrawn. "
                 f"Exploratory, with the BNPL supplement: best on every rail {ex5.get('best_on_every_rail')}. "
                 f"See rq5_pareto for the security versus friction trade-off |")
    e12 = _load("e12_summary") or {}
    if e12:
        d = e12["decision"]
        lines.append(
            f"| E12 author-written attacks: {d['comparison']} (decision rule e12/DECISION_RULE.md) | 1 | "
            f"{d['label']} | {d['attacks_in_model']} in-model attacks by {len(e12['authors'])} authors; "
            f"M2 {d['M2_losses']} losses, B7 {d['B7_losses']}; {d['loss_only_under_M2']} lost only under M2, "
            f"{d['loss_only_under_B7']} only under B7 (exact McNemar p = {d['p_exact_mcnemar']:.3g}); "
            f"rule wording \"{d['wording']}\" was written for an independent set and does not apply to this "
            f"author-written one (e12/ERRATA.md). First run reproduced: {e12['matches_first_run']} |")
    e11 = _load("e11_summary") or {}
    if e11:
        h6 = e11["H6"]
        a13 = e11["a13_bench"]
        lines.append(
            f"| H6 funded routes: rational-custodian A13 losses zero for every q in [0.3, 1] when q_hat <= q; refusal "
            f"<= {h6['b_threshold']} at capacity 1.5x mean exposure (hypotheses_v2.yaml) | 2 | "
            f"{_verdict(h6['supported'])}{' (smoke run, not evidence)' if e11.get('quick') else ''} | "
            f"(a) at most {h6['a_max_deviating']} rational custodians deviate over {h6['a_cells']} cells (oracle and "
            f"floor rules, provisioned); (b) worst refusal rate {h6['b_worst_refusal_rate']:.4f} at the reference "
            f"workload ({h6['reference_workload']} payments in flight). The optimistic rule (q_hat above q) lets "
            f"{h6['optimistic_rule_deviating_total']} custodian-cells deviate. PayeeBench A13: M3 loses "
            f"{a13['M3_losses']}/{a13['cases']}, M5 (M3 + F6) {a13['M5_losses']}/{a13['cases']} with "
            f"{a13['M5_refused']} refused. q is swept, not measured. Kill rule triggered: "
            f"{h6['kill_rule_triggered']} |")
    lines += ["", f"Formal models: {'all results as expected' if formal.get('all_as_expected') else 'see table'} "
              f"({formal.get('n', '?')} lemma results). F3 toy table: {toys.get('f3_matches_blueprint', '?')} rows "
              f"match the blueprint (the mismatch is corrected in the f3_toy caption). T4 mutation tests: "
              f"{toys.get('t4_pass', '?')} pass. E1 V1a/V1b agreement: {e1.get('agreement_allow_vs_block', '?')} on "
              f"allow vs block, {e1.get('agreement_exact_verdict', '?')} exact.", ""]

    # M1 vs B7 (where the advantage comes from)
    mc = _csv("e2_mcnemar")
    if mc is not None:
        rows = mc[(mc.B == "B7") & (mc.cases == "all in-model")]
        if len(rows):
            parts = [f"{r.A}: {r['loss under A only']} losses only under {r.A}, {r['loss under B only']} only under "
                     f"B7 (p = {r['p (exact McNemar)']})" for _, r in rows.iterrows()]
            lines += ["## Where the advantage over B7 comes from", "",
                      "Paired exact McNemar tests over all in-model cases against the strongest combined baseline: "
                      + "; ".join(parts) + ". V1 alone (M1) loses to B7 on these cases; the advantage over B7 comes "
                      "from V2 (anchoring, probation) and V3 (committed routes, receipts, scheduling), not from V1 "
                      "alone.", ""]

    lines += ["## Exploratory analyses (not pre-registered)", "",
              "* rq5_pareto, rq5_bnpl_supplement: security versus friction per rail, and a BNPL attack set built on a "
              "separate world after the pre-registered run.",
              "* e2_aip_external: payee-diversion scenarios specified by AIP-Bench, replayed on a separate world.",
              "* e4_string_weak: lookalikes with no name overlap, to test the visual and semantic signals.",
              "* e9_hosted_*, e9_synthetic_benign: hosted-model agents, an allowlist gate and synthetic benign "
              "payment tasks.",
              "* e10b_coverage: storefronts sampled from the Tranco list.", ""]

    lines += ["## Limitations computed from this run", ""] + [f"* {x}" for x in limitations(e6, e23, e7, e9)] + [""]

    xr = "not run"
    xt = _csv("x402_testnet")
    if xt is not None and len(xt):
        xr = (f"Base Sepolia through the public x402 facilitator (run {xmeta.get('run_date_utc', '?')}); see "
              "x402_testnet")
    lines += ["## Backends used in this run", "",
              f"* Card rail void latency: `{void.get('backend', '?')}`.",
              f"* Stablecoin rail: the E6 simulation settles x402 `exact` payments (real EIP-3009 / EIP-712 "
              f"signatures) on the in-process ledger with the escrow contract. Public testnet: {xr}. The escrow "
              f"contract runs on the local ledger only.",
              "* SEPA Instant and Verification of Payee: in-process sandbox following EPC VoP response codes.",
              f"* Agents in E9: {e9.get('hosted_models', 'scripted only')}; AgentDojo banking suite v1 executed "
              "with its own runtime and checks.",
              f"* CBA components: {'+'.join(cal.get('use', ['str', 'vis', 'sem']))} (embedding backend "
              f"{cal.get('embedding_backend', '?')}).",
              f"* E10 measured {e10.get('measured_utc', '?')}.",
              "* Real-world anchoring data: UCI PhiUSIIL phishing URL dataset (CC BY 4.0), fetched and checksummed by "
              "E4b.", ""]

    for title, tables, fig, note, evidence, paper in SECTIONS:
        lines += [f"## {title}", "", f"_Evidence: {'; '.join(evidence)}. Paper {paper}._", ""]
        if note:
            lines += [note, ""]
        if fig and os.path.exists(os.path.join(RESULTS, "figures", fig)):
            lines += [f"![{title}](figures/{fig})", ""]
        for t in tables:
            lines += [_table(t), ""]
    out = os.path.join(RESULTS, "REPORT.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return out


if __name__ == "__main__":
    print(build_report())
