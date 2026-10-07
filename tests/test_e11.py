"""E11 logic on a tiny copy of the model, and the pre-registration gating.
These runs use their own small parameters and write nothing under results/."""

import copy
import os
import shutil

import pytest

from experiments import e11_exposure as e11
from experiments import prereg


def tiny():
    P = copy.deepcopy(prereg.load_v2()["experiment"])
    P.update(custodians_per_cell=10, horizon_hold_times=12, warmup_hold_times=2)
    P["workloads"] = {"payments_in_flight": [10], "reference": 10}
    P["capacity_factors_reported"] = [2.0]
    P["coalition"]["draws_per_cell"] = 40
    P["bootstrap"]["resamples"] = 50
    return P


@pytest.fixture(scope="module")
def tabs():
    return e11.simulate(tiny(), seed=5)


def test_provisioned_rule_leaves_no_rational_deviation_when_q_hat_at_most_q(tabs):
    L = tabs["loss"]
    ok = L[(L.population == "provisioned") & (L.admission == "on") & (L.rule != "optimistic")]
    assert len(ok) and (ok.deviating == 0).all()


def test_admission_never_increases_losses(tabs):
    L = tabs["loss"]
    key = ["population", "workload", "rule", "q"]
    on = L[L.admission == "on"].set_index(key)
    off = L[L.admission == "off"].set_index(key)
    assert (on.deviating <= off.deviating).all()
    assert (on["gross loss / mean exposure"] <= off["gross loss / mean exposure"] + 1e-12).all()


def test_provisioned_refusal_does_not_depend_on_q(tabs):
    R = tabs["refusal"]
    p = R[R.population == "provisioned"]
    for rule, g in p.groupby("rule"):
        assert g["refused"].nunique() == 1 and g["payments"].nunique() == 1


def test_bond_requirement_rises_as_assumed_detection_falls(tabs):
    b = tabs["bond"].sort_values("q_hat")
    med = b["bond / mean exposure (median)"].tolist()
    assert all(x >= y - 1e-9 for x, y in zip(med, med[1:]))
    assert min(med) >= tiny()["capacity_factor"] - 1e-9  # coverage is a floor


def test_compromised_custodians_are_not_deterred_by_the_rule(tabs):
    C = tabs["compromised"]
    assert (C.deviating == C["compromised custodians"]).all()


def test_coalitions_of_one_do_not_profit_at_the_cap_but_the_full_route_can(tabs):
    C = tabs["coalition"]
    solo = C[(C["coalition size"] == 1) & (C.q_hat <= C.q)]
    assert (solo.rational == 0).all()
    assert C[C["coalition size"] == 3].rational.sum() >= C[C["coalition size"] == 1].rational.sum()


def test_h6_decision_uses_the_stated_criteria(tabs):
    P = tiny()
    h = e11.decide_h6(P, tabs, threshold=1.0)
    assert h["a_losses_zero"] and h["b_refusal_ok"] and h["supported"] and not h["kill_rule_triggered"]
    h0 = e11.decide_h6(P, tabs, threshold=-1.0)
    assert not h0["supported"] and h0["kill_rule_triggered"]


def test_paths_are_paired_across_passes():
    P = tiny()
    d = e11.draw_custodians(P, 3, 10, 5, 9000.0)[0]
    a, b = e11.run_path(P, d, None), e11.run_path(P, d, None)
    assert a.records == b.records and a.comp_x == b.comp_x
    capped = e11.run_path(P, d, 0.5 * a.records[-1])
    assert capped.records[-1] <= 0.5 * a.records[-1] + 1e-9 and capped.refused > 0


# ------------------------------------------------------------------ gating

def test_v2_gate_refuses_without_a_lock_and_accepts_a_matching_one(tmp_path, monkeypatch):
    v2, lock = tmp_path / "hypotheses_v2.yaml", tmp_path / "LOCK_V2"
    shutil.copy(prereg.V2, v2)
    monkeypatch.setattr(prereg, "V2", str(v2))
    monkeypatch.setattr(prereg, "V2_LOCK", str(lock))
    s = prereg.v2_status()
    assert not s["ok"] and "LOCK_V2" in s["reason"]
    with pytest.raises(RuntimeError):
        e11.run_e11()
    lock.write_text("0" * 64 + "\n")
    s = prereg.v2_status()
    assert not s["ok"] and "changed after it was locked" in s["reason"]
    assert prereg.lock_v2() == 1  # an existing lock is never overwritten
    lock.unlink()
    assert prereg.lock_v2() == 0
    assert prereg.v2_status()["ok"]
    v2.write_text(v2.read_text() + "\n# edited\n")
    assert not prereg.v2_status()["ok"]


def test_v2_gate_requires_the_recorded_v1_hash(tmp_path, monkeypatch):
    v2, lock = tmp_path / "hypotheses_v2.yaml", tmp_path / "LOCK_V2"
    v2.write_text(open(prereg.V2).read().replace(prereg.sha256_file(prereg.V1), "f" * 64))
    monkeypatch.setattr(prereg, "V2", str(v2))
    monkeypatch.setattr(prereg, "V2_LOCK", str(lock))
    assert prereg.lock_v2() == 1
    lock.write_text(prereg.sha256_file(str(v2)) + "\n")
    assert "v1_sha256" in prereg.v2_status()["reason"]


def test_every_number_e11_uses_comes_from_the_registration():
    spec = prereg.load_v2()
    assert spec["v1_sha256"] == prereg.sha256_file(prereg.V1)
    assert spec["hypotheses"]["H6"]["target"]["refusal_rate_legitimate_payments"]["max"] == 0.05
    assert spec["experiment"]["rules"]["oracle"]["q_hat"] == "q"
