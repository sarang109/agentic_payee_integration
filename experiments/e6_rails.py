"""E6 rail scheduling.

Post-authorization diversions are pushed through each rail's protocol stack:

  card         ISO 8583 authorization records (G1 observer), Stripe test mode
               or its simulator for authorize / void (manual capture)
  a2a_instant  VoP sandbox pre-check, instant credit transfer, camt.056-style
               recall, and an escrow account for the ESCROW mode
  stablecoin   x402 'exact' payments signed with EIP-3009 and settled on the
               local ledger, with the escrow contract for the ESCROW mode

For each rail, diversion class and mode (PRE, POST, ESCROW, and the mode RWS
chooses) we report detection before finality and residual loss, with
observer corruption f. Also: Theorem 3 probabilities per rail, the F4 toy
illustration, and measured void latency.
"""

from __future__ import annotations

import base64
import json
from typing import Dict, List

import numpy as np
import pandas as pd
from eth_account import Account

from meridian.issuers import Bank, make_entity
from meridian.core.status import StatusRegistry
from meridian.protocols import x402
from meridian.rws import ESCROW, POST, PRE, SchedulerParams, load_profiles, schedule
from meridian.rws.adapters import iso8583
from meridian.rws.adapters.sepa_inst import InstantTransfer, VoPSandbox
from meridian.rws.adapters.stripe_test import card_backend, measure_void_latency
from meridian.rws.window import empirical, fresh_safe_prob, post_safe_prob, toy_illustration

from .common import QUICK, SEED, Timer, write_csv, write_json, write_table


def _s(sampler, rng) -> float:
    return float(sampler(rng, 1)[0])


def card_run(profile, scenario: str, mode: str, f: int, rng, backend, iic_map) -> Dict:
    """scenario: first-hop (acquirer swap / laundering), custodian (onward
    deviation after capture), late-evidence (authority revoked after auth)."""
    amount = int(rng.integers(500, 50_000))
    committed = "proc:pspone/acct_000101"
    actual = "proc:acqrogue/acct_999001" if scenario == "first-hop" else committed
    acq, caid = actual.split(":", 1)[1].split("/")
    iic = {v: k for k, v in iic_map.items()}[acq]
    req = iso8583.authorization_request("4111111111111111", amount, "840", f"{rng.integers(1, 999999):06d}", "5661",
                                        iic, caid, "MERCHANT                 CITY        US")
    resp = iso8583.authorization_response(req)
    seen_first_hop = iso8583.first_hop_from_record(resp, iic_map)
    auth = backend.authorize(amount, metadata={"scenario": scenario})
    window = _s(profile.window, rng)
    detect = np.inf
    if scenario == "first-hop" and seen_first_hop != committed:
        lats = sorted(_s(o.latency, rng) for o in profile.observers_at(1))
        detect = lats[f] if f < len(lats) else np.inf
    elif scenario == "custodian":
        t_transfer = window + _s(profile.transfer_delay, rng)
        lats = sorted(_s(o.latency, rng) for o in profile.observers_at(3))
        detect = t_transfer + (lats[f] if f < len(lats) else np.inf)
    elif scenario == "late-evidence":
        detect = float(rng.uniform(30, 600))
    undone = False
    if mode == POST and np.isfinite(detect):
        d = _s(profile.decision, rng)
        if detect + d <= window:
            v = backend.void(auth["id"])
            undone = bool(v["ok"]) and detect + d + v["latency_s"] <= window
    return {"amount": amount, "detected_t": detect, "window": window, "undone": undone}


def a2a_run(profile, scenario: str, mode: str, f: int, rng, vop, instant, bank, ent, mule) -> Dict:
    amount = int(rng.integers(500, 50_000))
    acct = bank.open_account(ent) if scenario != "first-hop" else bank.open_account(mule)
    pre = vop.request(acct, party_name=ent.name)
    if mode == PRE and pre["matchResult"] != "MTCH":
        return {"amount": amount, "detected_t": 0.0, "window": 0.0, "undone": True, "blocked_pre": True}
    if mode == ESCROW:
        held_until = profile.escrow_window
        detect = float(rng.uniform(30, 600)) if scenario == "late-evidence" else (
            _s(profile.observers_at(4)[0].latency, rng) if scenario == "first-hop" else np.inf)
        undone = detect + _s(profile.decision, rng) + _s(profile.escrow_latency, rng) <= held_until
        return {"amount": amount, "detected_t": detect, "window": held_until, "undone": bool(undone)}
    tx = instant.send("debtor", acct, amount, 0.0)
    if scenario == "late-evidence":
        detect = float(rng.uniform(30, 600))
    elif scenario == "first-hop":
        lats = sorted(_s(o.latency, rng) for o in profile.observers_at(4))
        detect = tx["settled_at"] + (lats[f] if f < len(lats) else np.inf)
    else:
        detect = np.inf
    # SEPA Inst is final on acceptance (window 0): nothing can be undone before
    # finality; a recall request may still recover funds afterwards
    recovered = bool(mode == POST and np.isfinite(detect) and instant.recall(tx))
    return {"amount": amount, "detected_t": detect, "window": 0.0, "undone": False, "recovered_after_finality": recovered}


def coin_run(profile, scenario: str, mode: str, f: int, rng, chain: x402.LocalChain, payer, merchant_addr: str,
             attacker_addr: str, arbiter: str, now: int) -> Dict:
    amount = int(rng.integers(500, 50_000))
    pay_to = attacker_addr if scenario == "first-hop" else merchant_addr
    req = x402.payment_requirements(pay_to, amount, "https://merchant.example/item")
    if scenario == "first-hop":
        # a facilitator trying to redirect a signed authorization fails:
        # EIP-3009 binds `to` under the payer's signature
        honest = x402.payment_requirements(merchant_addr, amount, "https://merchant.example/item")
        hdr = x402.sign_payment(payer, honest, now)
        tampered = dict(honest, payTo=attacker_addr)
        p = x402.decode_header(hdr)
        p["payload"]["authorization"]["to"] = attacker_addr
        bad = base64.b64encode(json.dumps(p).encode()).decode()
        ok, why = chain.verify(bad, tampered, now)
        return {"amount": amount, "detected_t": 0.0, "window": 0.0, "undone": not ok, "blocked_pre": not ok,
                "note": why}
    if mode == ESCROW:
        hdr = x402.sign_payment(payer, req, now, to=chain.escrow_address)
        pid = f"pid-{rng.integers(1, 10**12)}"
        chain.settle(hdr, req, now, escrow_terms={"payment_id": pid, "payee": pay_to, "window": profile.escrow_window,
                                                   "arbiter": arbiter})
        detect = float(rng.uniform(30, 600)) if scenario == "late-evidence" else np.inf
        undone = False
        if np.isfinite(detect):
            t = now + detect + _s(profile.decision, rng) + _s(profile.escrow_latency, rng)
            undone = chain.refund(pid, arbiter, t)
        chain.release_due(now + profile.escrow_window + 10)
        return {"amount": amount, "detected_t": detect, "window": profile.escrow_window, "undone": bool(undone)}
    hdr = x402.sign_payment(payer, req, now)
    chain.settle(hdr, req, now)
    detect = float(rng.uniform(30, 600)) if scenario == "late-evidence" else np.inf
    return {"amount": amount, "detected_t": detect, "window": 0.0, "undone": False}


def run_e6() -> dict:
    profiles = load_profiles()
    rng = np.random.default_rng(SEED)
    n = 60 if QUICK else 400
    backend = card_backend(rng)
    with Timer(f"E6 void latency on card backend ({backend.backend})"):
        voids = measure_void_latency(backend, n=10 if QUICK else 30)
    write_csv("e6_void_latency", voids)
    vdf = pd.DataFrame(voids)
    if backend.backend != "simulator":
        profiles["card"].void = empirical(vdf.void_s.tolist())
        profiles["card"].void_success = float(vdf.void_ok.mean())
    # the Monte Carlo runs below never call a live API: they use the simulator
    # parameterised with the measured void latency and success
    from meridian.rws.adapters.stripe_test import StripeSimulator
    sim = StripeSimulator(rng, void_median_s=float(vdf.void_s.median()), void_success=float(vdf.void_ok.mean()))

    sr = StatusRegistry()
    bank = Bank("bnkeu1", sr)
    ent = make_entity("Velora GmbH", "5493000000000000AB12")
    mule = make_entity("Mule Holdings LLC", "5493000000000000CD34")
    vop = VoPSandbox({"bnkeu1": bank})
    instant = InstantTransfer(rng)
    chain = x402.LocalChain()
    payer = Account.from_key(bytes.fromhex("11" * 32))
    chain.mint(payer.address, 10**12)
    merchant_addr = Account.from_key(bytes.fromhex("22" * 32)).address
    attacker_addr = Account.from_key(bytes.fromhex("33" * 32)).address
    arbiter = Account.from_key(bytes.fromhex("44" * 32)).address
    iic_map = {"451234": "pspone", "459999": "acqrogue"}

    plan = {"card": ["first-hop", "custodian", "late-evidence"],
            "a2a_instant": ["first-hop", "late-evidence"],
            "stablecoin": ["first-hop", "late-evidence"]}
    rows: List[Dict] = []
    with Timer("E6 rail x scenario x mode x f simulations"):
        for rail, scenarios in plan.items():
            prof = profiles[rail]
            modes = [PRE, POST] + ([ESCROW] if prof.escrow_supported else [])
            for scen in scenarios:
                for f in (0, 1, 2):
                    for mode in modes + ["RWS"]:
                        for i in range(n):
                            m = mode
                            if mode == "RWS":
                                amt_guess = float(rng.integers(500, 50_000)) / 100
                                m = schedule(prof, amt_guess, 2, SchedulerParams(f=f)).mode
                            if rail == "card":
                                r = card_run(prof, scen, m, f, rng, sim, iic_map)
                            elif rail == "a2a_instant":
                                r = a2a_run(prof, scen, m, f, rng, vop, instant, bank, ent, mule)
                            else:
                                r = coin_run(prof, scen, m, f, rng, chain, payer, merchant_addr, attacker_addr,
                                             arbiter, 1_800_000_000 + i)
                            rows.append({"rail": rail, "scenario": scen, "f": f, "mode": mode, "chosen": m, **r})
    df = pd.DataFrame(rows)
    write_csv("e6_rail_runs", df.drop(columns=[c for c in ("note",) if c in df.columns]))
    agg = df.groupby(["rail", "scenario", "f", "mode"]).agg(n=("undone", "size"), undone=("undone", "sum")).reset_index()
    agg["detected+undone before finality"] = agg.apply(lambda r: f"{int(r.undone)}/{int(r.n)}", axis=1)
    agg["residual loss rate"] = (1 - agg.undone / agg.n).round(3)
    t0 = agg[agg.f == 0].pivot(index=["rail", "scenario"], columns="mode", values="residual loss rate")
    write_table("e6_residual_loss_f0", t0, "E6: residual loss rate per rail, diversion class and mode (f = 0)",
                "1.0 means no post-authorization diversion of this class was undone in time. 'first-hop' on "
                "stablecoin is stopped by the EIP-3009 signature binding before settlement.")
    tf = agg[(agg["mode"].isin([POST, "RWS"]))].pivot(index=["rail", "scenario", "mode"], columns="f",
                                                     values="residual loss rate")
    write_table("e6_observer_corruption", tf, "E6: residual loss vs number of corrupted observers f (POST and RWS)")
    rws_modes = df[df["mode"] == "RWS"].groupby(["rail", "f", "chosen"]).size().unstack(fill_value=0)
    write_table("e6_rws_choice", rws_modes, "E6: modes chosen by RWS (counts)")

    # Theorem 3 probabilities --------------------------------------------
    th = []
    for rail, prof in profiles.items():
        for f in (0, 1):
            lvl = 1 if prof.observers_at(1) else 4
            th.append({"rail": rail, "f": f,
                       "POST-safe prob (G1 observers)": round(post_safe_prob(prof.window_model(lvl), f=f, n=100_000), 4),
                       "FRESH-safe prob rho=60s": round(fresh_safe_prob(prof.window_model(lvl), 60, n=100_000), 4),
                       "FRESH-safe prob rho=300s": round(fresh_safe_prob(prof.window_model(lvl), 300, n=100_000), 4),
                       "ESCROW catch prob": round(post_safe_prob(prof.window_model(lvl, escrow=True), f=f, n=100_000), 4)
                       if prof.escrow_supported else None})
    write_table("e6_theorem3", pd.DataFrame(th), "E6: Theorem 3 quantities per rail (modelled latencies, config/rails.yaml)",
                index=False)
    toy = toy_illustration()
    write_table("f4_toy", pd.DataFrame([{
        "condition": "original (report only)", "blueprint": "100%", "this run": f"{toy['original_condition']:.1%}"}, {
        "condition": "corrected, honest observers", "blueprint": "79%", "this run": f"{toy['corrected_honest']:.1%}"}, {
        "condition": "corrected, fastest observer corrupted", "blueprint": "48%",
        "this run": f"{toy['corrected_fastest_corrupted']:.1%}"}, {
        "condition": "stale-authority catch, rho = 3", "blueprint": "67%", "this run": f"{toy['fresh_rho_3']:.1%}"}]),
        "F4 toy illustration", f"Parameters: {toy['parameters']}", index=False)

    vlat = {"backend": backend.backend, "void_p50_s": float(vdf.void_s.median()), "void_p95_s": float(vdf.void_s.quantile(0.95)),
            "void_success": float(vdf.void_ok.mean())}
    summary = {"void": vlat, "toy": toy}
    card_fh = agg[(agg.rail == "card") & (agg.scenario == "first-hop") & (agg.f == 0) & (agg["mode"] == POST)]
    inst_post = agg[(agg.rail != "card") & (agg.scenario == "late-evidence") & (agg["mode"] == POST)]
    inst_esc = agg[(agg.rail != "card") & (agg.scenario == "late-evidence") & (agg["mode"] == ESCROW)]
    card_rate = card_fh.undone.sum() / max(1, card_fh.n.sum())
    card_post_safe = post_safe_prob(profiles["card"].window_model(1), 0, n=100_000)
    summary["H3"] = {
        "card_post_safe_probability": round(card_post_safe, 4),
        "card_first_hop_POST_undone": f"{int(card_fh.undone.sum())}/{int(card_fh.n.sum())}",
        "instant_late_evidence_POST_undone": f"{int(inst_post.undone.sum())}/{int(inst_post.n.sum())}",
        "instant_late_evidence_ESCROW_undone": f"{int(inst_esc.undone.sum())}/{int(inst_esc.n.sum())}",
        "supported": bool(card_post_safe >= 0.99 and card_rate >= 0.99 and inst_post.undone.sum() == 0
                          and inst_esc.undone.sum() > 0),
    }
    write_json("e6_summary", summary)
    return summary


if __name__ == "__main__":
    print(run_e6())
