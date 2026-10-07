"""Checks for the H5 verdict, the E9 gates, the supplementary attack sets
and the x402 testnet request helpers."""

import base64
import json
import random

import pandas as pd
from eth_account import Account

from experiments.e2_e3 import best_sets, h5_verdict, pareto_table
from experiments.e9_hosted import ATTACKER_IBAN, gate_verdict
from meridian.protocols import x402


def _rt(rows):
    return pd.DataFrame(rows, columns=["rail", "config", "attack_loss", "loss_rate", "benign_step_up",
                                       "benign_false_block", "p95_decision_ms"])


def test_h5_keeps_ties_and_skips_rails_without_attacks():
    rt = _rt([
        ("card", "M1", "5/10", 0.5, 0.0, 0, 1.0), ("card", "M2", "1/10", 0.1, 0.2, 0, 3.0),
        ("card", "M3", "1/10", 0.1, 0.2, 0, 2.0),
        ("bnpl", "M1", "0/0", float("nan"), 0.0, 0, 0.5), ("bnpl", "M2", "0/0", float("nan"), 0.0, 0, 3.0),
        ("bnpl", "M3", "0/0", float("nan"), 0.0, 0, 3.0),
    ])
    assert best_sets(rt) == {"card": ["M2", "M3"]}
    v = h5_verdict(rt)
    assert v["rails_without_attack_cases"] == ["bnpl"]
    assert v["supported"] is False  # M2 and M3 are best on every rail with data
    assert v["legacy_supported"] is True  # the old latency tie-break said otherwise


def test_h5_supported_when_no_config_is_best_everywhere():
    rt = _rt([
        ("card", "M1", "5/10", 0.5, 0.0, 0, 1.0), ("card", "M3", "1/10", 0.1, 0.2, 0, 2.0),
        ("wallet", "M1", "0/10", 0.0, 0.0, 0, 1.0), ("wallet", "M3", "0/10", 0.0, 0.3, 0, 2.0),
    ])
    assert h5_verdict(rt)["supported"] is True


def test_pareto_marks_dominated_configs():
    rt = _rt([("card", "M1", "5/10", 0.5, 0.1, 0, 1.0), ("card", "M2", "5/10", 0.5, 0.2, 0, 1.0),
              ("card", "M3", "1/10", 0.1, 0.2, 0, 2.0)])
    t = pareto_table(rt).set_index("config")["on the frontier"]
    assert t["M1"] == "yes" and t["M3"] == "yes" and t["M2"] == ""


class _Gate:
    def decide(self, recipient, allowed, brands):
        return "ALLOW" if recipient in allowed else "STEP-UP"


def test_gate_verdicts():
    hist = {"H1"}
    assert gate_verdict("none", ATTACKER_IBAN, set(), set(), hist, _Gate()) == "ALLOW"
    assert gate_verdict("blocklist", ATTACKER_IBAN, set(), set(), hist, _Gate()) == "DENY"
    assert gate_verdict("blocklist", "NEW", set(), set(), hist, _Gate()) == "ALLOW"
    assert gate_verdict("allowlist", "H1", set(), set(), hist, _Gate()) == "ALLOW"
    assert gate_verdict("allowlist", "TYPED", {"TYPED"}, set(), hist, _Gate()) == "STEP-UP"
    assert gate_verdict("MERIDIAN", "TYPED", {"TYPED"}, set(), hist, _Gate()) == "ALLOW"


def test_supplementary_sets_are_built_on_the_intended_routes():
    from payeebench.cases import AIP_SCENARIOS, AttackerKit, gen_aip_external, gen_bnpl
    from payeebench.world import World

    w = World(seed=3).build()
    rng = random.Random(3)
    kit = AttackerKit(w, rng)
    bn = gen_bnpl(w, kit, rng, 8)
    assert len(bn) == 8 and {c.rail for c in bn} == {"bnpl"}
    assert all(c.variant.startswith("bnpl:") for c in bn)
    ext = gen_aip_external(w, kit, rng, 2)
    assert len(ext) == 2 * len(AIP_SCENARIOS)
    assert {c.rail for c in ext if c.variant.startswith("AIP:V9")} == {"stablecoin"}
    assert all(c.swap_after_mandate for c in ext if c.variant.startswith("AIP:A-AP2-11"))


def test_x402_tampered_recipient_breaks_signature():
    payer = Account.from_key(bytes.fromhex("11" * 32))
    merchant = Account.from_key(bytes.fromhex("22" * 32)).address
    attacker = Account.from_key(bytes.fromhex("33" * 32)).address
    req = x402.payment_requirements(merchant, 10_000, "https://merchant.example/item")
    hdr = x402.sign_payment(payer, req, 1_800_000_000)
    chain = x402.LocalChain()
    chain.mint(payer.address, 10**9)
    p = x402.decode_header(hdr)
    p["payload"]["authorization"]["to"] = attacker
    bad = base64.b64encode(json.dumps(p).encode()).decode()
    ok, _ = chain.verify(bad, dict(req, payTo=attacker), 1_800_000_000)
    assert not ok
    ok, _ = chain.verify(hdr, req, 1_800_000_000)
    assert ok
