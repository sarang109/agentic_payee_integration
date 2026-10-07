"""Funded routes (F6): closed forms, an independent value-iteration check,
and the admission ledger."""

import math

import pytest

from meridian.core.exposure import (INF, Custodian, FundedRoutes, admission_cap, coalition_detection, coalition_q,
                                    per_hop_detection,
                                    coalition_rational, deterrence_cap, deviation_cost, deviation_threshold, hold_time_threshold,
                                    rational_to_deviate, required_bond)


def C(bond=100.0, margin=1.0, beta=0.95, hold=3.0, name="c"):
    return Custodian(name, bond, margin, beta, hold)


# ------------------------------------------------------------------ value iteration

def vi_deviates_first(c: Custodian, exposure: float, q: float, iters: int = 20000) -> bool:
    """Solve the custodian's infinite-horizon problem by value iteration and
    return whether stealing is the optimal first move. Each period: operate
    honestly (earn the margin, continue) or steal (with probability 1 - q
    receive the exposure and continue; with probability q the franchise ends
    and the bond is slashed after the hold time)."""
    V = 0.0
    for _ in range(iters):
        honest = c.margin + c.beta * V
        steal = (1 - q) * (exposure + c.beta * V) - q * c.beta ** c.hold * c.bond
        V_new = max(honest, steal)
        if abs(V_new - V) < 1e-12:
            V = V_new
            break
        V = V_new
    honest = c.margin + c.beta * V
    steal = (1 - q) * (exposure + c.beta * V) - q * c.beta ** c.hold * c.bond
    return steal > honest + 1e-9


def vi_threshold(c: Custodian, q: float) -> float:
    lo, hi = 0.0, 1e5
    for _ in range(60):
        mid = (lo + hi) / 2
        if vi_deviates_first(c, mid, q):
            hi = mid
        else:
            lo = mid
    return hi


@pytest.mark.parametrize("q", [0.3, 0.5, 0.8])
@pytest.mark.parametrize("params", [
    dict(bond=50.0, margin=1.0, beta=0.9, hold=2.0),
    dict(bond=200.0, margin=2.0, beta=0.95, hold=5.0),
    dict(bond=0.0, margin=0.5, beta=0.8, hold=0.0),
])
def test_closed_form_matches_value_iteration(params, q):
    c = C(**params)
    closed = deterrence_cap(c, q)
    solved = vi_threshold(c, q)
    assert solved == pytest.approx(closed, rel=1e-4, abs=1e-4)


def test_value_iteration_agrees_on_either_side_of_the_cap():
    c, q = C(), 0.6
    cap = deterrence_cap(c, q)
    assert not vi_deviates_first(c, cap * 0.99, q)
    assert vi_deviates_first(c, cap * 1.01, q)
    assert rational_to_deviate(c, cap * 1.01, q) and not rational_to_deviate(c, cap * 0.99, q)


# ------------------------------------------------------------------ closed forms

def test_certain_detection_deters_any_exposure():
    c = C()
    assert deterrence_cap(c, 1.0) == INF
    assert not rational_to_deviate(c, 1e12, 1.0)
    assert admission_cap(c, 1.0) == c.bond  # coverage still binds


def test_cap_is_monotone_in_detection_and_bond():
    c = C()
    caps = [deterrence_cap(c, q) for q in (0.0, 0.3, 0.6, 0.9)]
    assert caps == sorted(caps) and caps[0] == pytest.approx(c.margin)
    assert deterrence_cap(C(bond=500.0), 0.5) > deterrence_cap(C(bond=50.0), 0.5)


def test_longer_hold_discounts_the_bond_and_lowers_the_cap():
    assert deterrence_cap(C(hold=1.0), 0.5) > deterrence_cap(C(hold=10.0), 0.5)


def test_hold_time_threshold_is_consistent_with_the_cap():
    c, q = C(bond=100.0, hold=0.0), 0.5
    X = deterrence_cap(c, q) * 0.9
    T = hold_time_threshold(c, X, q)
    assert T is not None
    # at the threshold, exposure X sits exactly on the cap
    at = Custodian("c", c.bond, c.margin, c.beta, T if T != INF else 0.0)
    if T != INF:
        assert deterrence_cap(at, q) == pytest.approx(X, rel=1e-9)
        longer = Custodian("c", c.bond, c.margin, c.beta, T + 1)
        assert rational_to_deviate(longer, X, q)


def test_hold_time_threshold_edge_cases():
    c = C(bond=10.0)
    assert hold_time_threshold(c, 0.5, 0.5) == INF  # margin alone covers it
    assert hold_time_threshold(c, 1e6, 0.5) is None  # bond far too small even at T=0
    assert hold_time_threshold(C(bond=0.0), 1e6, 0.5) is None
    assert hold_time_threshold(c, 100.0, 0.0) is None  # nothing is ever detected


def test_required_bond_hits_the_target_cap_exactly():
    for q in (0.3, 0.5, 0.8, 1.0):
        for target in (10.0, 100.0, 1000.0):
            B = required_bond(1.0, 0.95, 3.0, q, target)
            assert admission_cap(Custodian("c", B, 1.0, 0.95, 3.0), q) == pytest.approx(target, rel=1e-9)
    # a smaller bond falls short
    B = required_bond(1.0, 0.95, 3.0, 0.5, 100.0)
    assert admission_cap(Custodian("c", B * 0.9, 1.0, 0.95, 3.0), 0.5) < 100.0


def test_required_bond_rises_as_detection_falls():
    bonds = [required_bond(1.0, 0.95, 3.0, q, 1000.0) for q in (1.0, 0.8, 0.5, 0.3)]
    assert bonds == sorted(bonds)
    assert required_bond(1.0, 0.95, 3.0, 0.0, 1000.0) == INF


def test_input_validation():
    with pytest.raises(ValueError):
        Custodian("c", 1.0, 1.0, 1.0, 1.0)
    with pytest.raises(ValueError):
        Custodian("c", -1.0, 1.0, 0.9, 1.0)
    with pytest.raises(ValueError):
        deviation_cost(C(), 1.5)


# ------------------------------------------------------------------ admission

def test_admission_enforces_the_cap_and_releases_after_the_hold():
    c = C(bond=100.0, hold=10.0)
    fr = FundedRoutes([c], q_hat=0.5)
    cap = fr.cap("c")
    assert cap == min(deterrence_cap(c, 0.5), 100.0)
    a = fr.admit("c", cap * 0.6, t=0.0)
    assert a.admitted and a.exposure_before == 0.0
    assert not fr.admit("c", cap * 0.6, t=5.0).admitted  # 0.6 + 0.6 > cap while held
    assert fr.exposure("c", 5.0) == pytest.approx(cap * 0.6)
    assert fr.admit("c", cap * 0.6, t=10.0).admitted  # first payment released at t = 10
    assert fr.admit("c", 0.0, t=11.0).admitted


def test_refusal_does_not_change_exposure():
    fr = FundedRoutes([C(bond=10.0)], q_hat=0.5)
    assert not fr.admit("c", 11.0, 0.0).admitted
    assert fr.exposure("c", 0.0) == 0.0


def test_admission_never_leaves_a_rational_deviation_when_q_hat_is_at_most_q():
    """Property: whatever is admitted, a custodian whose true detection
    probability is at least q_hat has no profitable theft."""
    import random
    rng = random.Random(1)
    for _ in range(200):
        c = Custodian("c", rng.uniform(0, 500), rng.uniform(0.1, 5), rng.uniform(0.7, 0.99), rng.uniform(0, 10))
        q_hat = rng.uniform(0.1, 1.0)
        q_true = rng.uniform(q_hat, 1.0)
        fr = FundedRoutes([c], q_hat)
        t = 0.0
        for _ in range(60):
            t += rng.expovariate(1.0)
            fr.admit("c", rng.lognormvariate(3, 1), t)
            assert not rational_to_deviate(c, fr.exposure("c", t), q_true)


def test_admission_is_not_safe_when_q_hat_overstates_detection():
    c = C(bond=1000.0, hold=5.0)
    fr = FundedRoutes([c], q_hat=0.9)
    cap = fr.cap("c")
    assert fr.admit("c", cap, 0.0).admitted
    assert rational_to_deviate(c, fr.exposure("c", 1.0), 0.3)


def test_per_custodian_q_hat_and_duplicates():
    a, b = C(name="a"), C(name="b")
    fr = FundedRoutes([a, b], {"a": 0.3, "b": 0.9})
    assert fr.cap("a") < fr.cap("b")
    with pytest.raises(ValueError):
        FundedRoutes([a, a], 0.5)


# ------------------------------------------------------------------ coalitions

def test_coalition_detection():
    assert coalition_detection([], 0.0) == 0.0
    assert coalition_detection([0.5, 0.5]) == pytest.approx(0.75)
    assert coalition_detection([0.5], external=0.2) == pytest.approx(1 - 0.5 * 0.8)


def test_coalition_can_profit_where_no_single_custodian_can():
    members = [C(name=f"c{i}") for i in range(3)]
    q = 0.6
    cap = admission_cap(members[0], q)
    exposures = [cap] * 3  # every member exactly at its individual cap
    assert not any(rational_to_deviate(m, x, q) for m, x in zip(members, exposures))
    # the coalition hides its own evidence, so detection falls to the external channel
    q_coal = coalition_detection([], external=0.1)
    assert coalition_rational(members, exposures, q_coal)
    # and if enough honest custodians remain on the route, it does not pay
    assert not coalition_rational(members, exposures, q)


def test_per_hop_detection_round_trips_and_coalitions_lose_evidence():
    for q in (0.3, 0.6, 0.9):
        p = per_hop_detection(q, 3, 0.1)
        assert 1 - 0.9 * (1 - p) ** 2 == pytest.approx(q)
        assert coalition_q(q, 3, 1, 0.1) == pytest.approx(q)
        qs = [coalition_q(q, 3, k, 0.1) for k in (1, 2, 3)]
        assert qs == sorted(qs, reverse=True)
        assert qs[2] == pytest.approx(0.1)
    assert per_hop_detection(0.05, 3, 0.1) == 0.0  # already explained by the external channel
    with pytest.raises(ValueError):
        coalition_q(0.5, 3, 4)


def test_a_custodian_exactly_at_its_cap_is_indifferent_and_counts_as_honest():
    for q in (0.3, 0.55, 0.8):
        c = C(bond=137.0, hold=2.5)
        cap = deterrence_cap(c, q)
        assert not rational_to_deviate(c, cap, q)
        assert not rational_to_deviate(c, cap * (1 + 1e-12), q)
        assert rational_to_deviate(c, cap * 1.001, q)
        assert deviation_threshold(c, q) >= cap
