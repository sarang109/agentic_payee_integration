"""Commitments must cover the payment's amount and currency; a binding token is
single use when the verifier keeps a spent-nonce store."""

import dataclasses

from meridian.core.canon import canonical
from meridian.core import ALLOW, DENY, G2, RAP, STEP_UP, Policy, RouteBundle, SpentNonces, pav, verify_route
from meridian.core.routes import PAYOUT
from tests.test_core_s1 import build, payment, snaps

ANCHOR = "brand:brandx.com"


def routed(w, pay, amount=None, currency=None):
    beta = w["psp"].binding_token(pay)
    rap = RAP([w["e0"], w["e1"]], snaps(w, [w["e0"], w["e1"]], pay.t), beta)
    c = w["psp"].commit(pay, w["p"], w["acct"], beta.digest, kind=PAYOUT, amount=amount)
    if currency is not None:
        c = dataclasses.replace(c, currency=currency)
        c = dataclasses.replace(c, sig=w["psp"].key.sign(canonical(c.body())))
    return RouteBundle(rap, [], [c], w["term"], snaps(w, [w["term"]], pay.t))


def test_commitment_matching_the_payment_is_allowed():
    w = build()
    pay = payment(w)
    d = verify_route(routed(w, pay), pay, ANCHOR, Policy(), w["trust"])
    assert d.verdict == ALLOW and d.level == G2, d.reasons


def test_commitment_for_a_smaller_amount_steps_up():
    w = build()
    pay = payment(w)
    d = verify_route(routed(w, pay, amount=pay.amount - 1), pay, ANCHOR, Policy(), w["trust"])
    assert d.verdict == STEP_UP and d.reasons == ["commitment-amount"]


def test_commitment_for_a_larger_amount_steps_up():
    w = build()
    pay = payment(w)
    d = verify_route(routed(w, pay, amount=pay.amount + 1), pay, ANCHOR, Policy(), w["trust"])
    assert d.verdict == STEP_UP and d.reasons == ["commitment-amount"]


def test_commitment_in_another_currency_steps_up():
    w = build()
    pay = payment(w)
    d = verify_route(routed(w, pay, currency="EUR"), pay, ANCHOR, Policy(), w["trust"])
    assert d.verdict == STEP_UP and d.reasons == ["commitment-currency"]


def test_pav_claims_the_token_once():
    w = build()
    pay = payment(w)
    rap = RAP([w["e0"], w["e1"]], snaps(w, [w["e0"], w["e1"]], pay.t), w["psp"].binding_token(pay))
    spent = SpentNonces()
    assert pav(rap, pay, ANCHOR, Policy(), w["trust"], spent).verdict == ALLOW
    d = pav(rap, pay, ANCHOR, Policy(), w["trust"], spent)
    assert d.verdict == DENY and d.reasons == ["nonce-spent"]
    # without a store nothing changes
    assert pav(rap, pay, ANCHOR, Policy(), w["trust"]).verdict == ALLOW


def test_verify_route_claims_the_token_once():
    w = build()
    pay = payment(w)
    bundle = routed(w, pay)
    spent = SpentNonces()
    assert verify_route(bundle, pay, ANCHOR, Policy(), w["trust"], spent=spent).verdict == ALLOW
    d = verify_route(bundle, pay, ANCHOR, Policy(), w["trust"], spent=spent)
    assert d.verdict == DENY and d.reasons == ["nonce-spent"]


def test_a_refused_payment_does_not_burn_the_token():
    w = build()
    pay = payment(w)
    good = routed(w, pay)
    no_commitment = RouteBundle(good.rap, [], [], w["term"], good.status)
    spent = SpentNonces()
    assert verify_route(no_commitment, pay, ANCHOR, Policy(), w["trust"], spent=spent).verdict == STEP_UP
    assert len(spent) == 0
    assert verify_route(good, pay, ANCHOR, Policy(), w["trust"], spent=spent).verdict == ALLOW


def test_spent_entries_are_pruned_after_expiry():
    w = build()
    pay = payment(w)
    beta = w["psp"].binding_token(pay)
    spent = SpentNonces()
    assert spent.claim(beta, pay.t) and not spent.claim(beta, pay.t)
    other = dataclasses.replace(beta, nonce="later")
    assert spent.claim(other, beta.exp + 1)
    assert len(spent) == 1
