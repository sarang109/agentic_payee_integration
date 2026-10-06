"""Assemble results/REPORT.md from the generated tables and summaries.

Every number in the report comes from a file under results/; the text only
says where to look and what each table measures.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from .common import RAW, RESULTS, TABLES

SECTIONS = [
    ("Mechanized verification", ["formal_results"], None,
     "Tamarin models of the RAP exchange (T1, T2, T4), committed routes and attributability (T10, T11), and the "
     "AP2/ACP-style checkout with and without the extension (P10, P18); ProVerif equivalence for the private lookup."),
    ("F3 toy check, T4 mutation tests, F5 split hardness", ["f3_toy", "t4_mutations", "f5_split"], None, ""),
    ("E1 V1a directory vs V1b proof-carrying", ["e1_latency", "e1_disagreements", "e1_outage_lying", "e1_leakage"],
     None, ""),
    ("E2 attack matrix", ["e2_attack_matrix_loss", "e2_attack_matrix_stepup", "e2_by_variant", "e2_premise_violation",
                          "e2_mcnemar"], "e2_attack_heatmap.png", ""),
    ("E3 legitimate structures", ["e3_false_block", "e3_step_up", "e3_stepup_causes", "e3_stepup_exposure",
                                  "e3_rates_bootstrap"], None, ""),
    ("RQ5 per-rail comparison", ["rq5_per_rail"], None, ""),
    ("E4 anchoring calibration", ["e4_detection_auc", "e4_by_technique", "e4_ablation_heldout", "e4_prevalence"],
     "e4_cba_tradeoff.png", ""),
    ("E5 probation sweep", ["e5_probation", "e5_monitor_reaction", "e5_cap"], "e5_probation.png", ""),
    ("E6 rail scheduling", ["e6_residual_loss_f0", "e6_observer_corruption", "e6_rws_choice", "e6_theorem3", "f4_toy"],
     "e6_rail_residual.png", ""),
    ("E7 privacy cost (V4) and H4", ["e7_latency", "e7_sizes", "e7_lookups", "e7_h4_disagreements", "e7_leakage"], None,
     ""),
    ("E8 scalability", ["e8_pav", "e8_directory", "e8_log"], None, ""),
    ("E9 agent containment", ["e9_agentdojo", "e9_agentdojo_benign", "e9_compromise_vs_payment", "e9_marketplace"],
     None, ""),
    ("E10 coverage in the wild", ["e10_coverage", "e10_lookalike_prevalence"], None, ""),
    ("Ablations", ["ablation1_bilateral", "ablation2_scope_meet", "ablation3_rho"], None,
     "Ablation 4 (probation) is E5, 5 (observers and collusion) is E6, 6 (RAP vs directory) is E1."),
]


def _load(name: str, folder: str = RAW) -> Optional[dict]:
    p = os.path.join(folder, f"{name}.json")
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


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


def build_report() -> str:
    status = _load("run_status", RESULTS) or {}
    e23 = _load("e2_e3_summary") or {}
    e6 = _load("e6_summary") or {}
    e7 = _load("e7_summary") or {}
    e9 = _load("e9_summary") or {}
    formal = _load("formal_summary") or {}
    toys = _load("toys_summary") or {}
    e1 = _load("e1_summary") or {}
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
              "| hypothesis | verdict | evidence |", "|---|---|---|"]
    h1, h2, h5 = e23.get("H1", {}), e23.get("H2", {}), e23.get("H5", {})
    lines.append(f"| H1 V1 admits no out-of-closure payee; baselines do; false blocks <= 1% | "
                 f"{_verdict(h1.get('supported'))} | M1 loss on A3/A4/A5/A7/A8: {h1.get('m1_loss_on_v1_classes')}; "
                 f"baselines: {h1.get('baseline_losses_on_v1_classes')}; M1 false-block rate {h1.get('m1_false_block_rate')} |")
    lines.append(f"| H2 V2 lowers lookalike success; benign step-up <= 5% | {_verdict(h2.get('supported'))} | "
                 f"A1-A2 loss M2 {h2.get('m2_loss_A1_A2')} vs M1 {h2.get('m1_loss_A1_A2')} (McNemar p = "
                 f"{h2.get('mcnemar_p')}); benign CBA step-up {h2.get('benign_cba_step_up')} (bench: 35% of brands "
                 f"impersonated; E4 reports the prevalence curve) |")
    h3 = e6.get("H3", {})
    lines.append(f"| H3 card POST detection when POST-safe holds; instant rails need PRE or escrow | "
                 f"{_verdict(h3.get('supported'))} | card POST-safe probability {h3.get('card_post_safe_probability')}, "
                 f"first-hop voided {h3.get('card_first_hop_POST_undone')}; instant late evidence: POST undone "
                 f"{h3.get('instant_late_evidence_POST_undone')}, ESCROW undone {h3.get('instant_late_evidence_ESCROW_undone')} |")
    h4 = e7.get("H4", {})
    lines.append(f"| H4 V4 keeps decisions; payer p95 <= 150 ms | {_verdict(h4.get('supported'))} | agreement "
                 f"{h4.get('exact_verdict_agreement')} on {h4.get('cases')} cases; payer-side p95 "
                 f"{h4.get('added_payer_p95_ms') and round(h4.get('added_payer_p95_ms'), 1)} ms; prover p95 "
                 f"{h4.get('prover_p95_ms') and round(h4.get('prover_p95_ms'))} ms |")
    lines.append(f"| H5 no single version dominates every rail | {_verdict(h5.get('supported'))} | best MERIDIAN "
                 f"configuration per rail: {h5.get('best_meridian_config_per_rail')} |")
    lines += ["", f"Formal models: {'all results as expected' if formal.get('all_as_expected') else 'see table'} "
              f"({formal.get('n', '?')} lemma results). F3 toy table: {toys.get('f3_matches_blueprint', '?')} rows "
              f"match the blueprint. T4 mutation tests: {toys.get('t4_pass', '?')} pass. E1 V1a/V1b agreement: "
              f"{e1.get('agreement_allow_vs_block', '?')} on allow vs block, {e1.get('agreement_exact_verdict', '?')} exact.",
              ""]

    lines += ["## Backends used in this run", "",
              f"* Card rail void latency: `{(e6.get('void') or {}).get('backend', '?')}` "
              "(set STRIPE_SECRET_KEY=sk_test_... to measure on Stripe test mode).",
              "* Stablecoin rail: x402 `exact` payments with real EIP-3009 / EIP-712 signatures, settled on the "
              "in-process ledger (`LocalChain`) with the escrow contract; no public testnet.",
              "* SEPA Instant and Verification of Payee: in-process sandbox following EPC VoP response codes.",
              f"* Agents in E9: {e9.get('hosted_models', 'scripted')}; AgentDojo banking suite v1 executed with "
              "its own runtime and security checks.",
              "* Embeddings for CBA: see results/raw/cba_calibration.json (`embedding_backend`).", ""]

    for title, tables, fig, note in SECTIONS:
        lines += [f"## {title}", ""]
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
