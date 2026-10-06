from meridian.core import ALLOW, DENY, G2, STEP_UP, RAP, Payment, Policy, RouteBundle, Scope, TrustStore, pav, verify_route
from meridian.core.status import StatusRegistry
from meridian.issuers import QVI, Bank, DomainVerifier, PSPOperator, make_entity

DAY = 86400


def build():
    sr = StatusRegistry()
    trust = TrustStore()
    dv = DomainVerifier("dv1", sr)
    qvi = QVI("qvi1", sr)
    psp = PSPOperator("stripe", sr)
    bank = Bank("bnk1", sr)
    for i in (dv, qvi, psp, bank):
        i.register(trust)
    brandx = make_entity("BrandX Inc", "5493001KJTIIGC8Y1R12")
    mallory = make_entity("Mallory LLC", "5493009ZZTIIGC8Y1R99")
    for ent in (brandx, mallory):
        trust.add_role_credential(qvi.role_credential(ent, 1000 * DAY))
    dns = {}
    val = dv.challenge("brandx.com", brandx.rep)
    dns["_meridian-challenge.brandx.com"] = [val]
    e0 = dv.bind("brandx.com", brandx, dns, 0, 400 * DAY)
    p = psp.new_account()
    e1 = psp.issue("AG", brandx.lei_id, p, Scope.make(rails={"card"}, currencies={"USD"}, ceiling=500_000),
                   0, 400 * DAY, psp.key, signing_key=brandx.rep)
    acct = bank.open_account(brandx)
    term = bank.terminal_binding(acct, 0, 400 * DAY)
    evil_acct = bank.open_account(mallory)
    evil_term = bank.terminal_binding(evil_acct, 0, 400 * DAY)
    return locals()


def payment(w, t=10 * DAY, payee=None):
    return Payment("pay1", payee or w["p"], "card", "USD", 12_000, "5661", "US", t, "cart-digest", "n1")


def snaps(w, edges, t):
    return {e.status.list_id: w["sr"].lists[e.status.list_id].snapshot(t) for e in edges}


def test_pav_allows_direct_card_merchant():
    w = build()
    pay = payment(w)
    rap = RAP([w["e0"], w["e1"]], snaps(w, [w["e0"], w["e1"]], pay.t), w["psp"].binding_token(pay))
    d = pav(rap, pay, "brand:brandx.com", Policy(), w["trust"])
    assert d.verdict == ALLOW, d.reasons
    assert d.sig_checks >= 2 * 2 + 1


def test_route_g2_and_payout_change_is_denied():
    w = build()
    pay = payment(w)
    beta = w["psp"].binding_token(pay)
    rap = RAP([w["e0"], w["e1"]], snaps(w, [w["e0"], w["e1"]], pay.t), beta)
    good = RouteBundle(rap, [], [w["psp"].payout_attestation(pay, w["p"], w["acct"], beta.digest)], w["term"],
                       snaps(w, [w["term"]], pay.t))
    d = verify_route(good, pay, "brand:brandx.com", Policy(), w["trust"])
    assert d.verdict == ALLOW and d.level == G2, d.reasons
    # X3: payout account switched to an account held by someone else
    pay2 = Payment("pay2", w["p"], "card", "USD", 12_000, "5661", "US", pay.t, "cart-digest", "n2")
    beta2 = w["psp"].binding_token(pay2)
    rap2 = RAP([w["e0"], w["e1"]], snaps(w, [w["e0"], w["e1"]], pay2.t), beta2)
    bad = RouteBundle(rap2, [], [w["psp"].payout_attestation(pay2, w["p"], w["evil_acct"], beta2.digest)],
                      w["evil_term"], snaps(w, [w["evil_term"]], pay2.t))
    d = verify_route(bad, pay2, "brand:brandx.com", Policy(), w["trust"])
    assert d.verdict == DENY, d.reasons
    # X6: no onward commitment -> step-up at G1
    none = RouteBundle(rap, [], [], w["term"], snaps(w, [w["term"]], pay.t))
    d = verify_route(none, pay, "brand:brandx.com", Policy(), w["trust"])
    assert d.verdict == STEP_UP and d.level == 1


def test_payee_swap_breaks_binding():
    w = build()
    pay = payment(w)
    rap = RAP([w["e0"], w["e1"]], snaps(w, [w["e0"], w["e1"]], pay.t), w["psp"].binding_token(pay))
    swapped = payment(w, payee="proc:stripe/acct_999999")
    d = pav(rap, swapped, "brand:brandx.com", Policy(), w["trust"])
    assert d.verdict == DENY


def test_revoked_edge_steps_up():
    w = build()
    pay = payment(w)
    w["psp"].revoke(w["e1"], pay.t - 3600)
    rap = RAP([w["e0"], w["e1"]], snaps(w, [w["e0"], w["e1"]], pay.t), w["psp"].binding_token(pay))
    d = pav(rap, pay, "brand:brandx.com", Policy(), w["trust"])
    assert d.verdict == STEP_UP and "revoked" in d.reasons


def test_operator_refuses_second_commitment():
    import pytest
    w = build()
    pay = payment(w)
    beta = w["psp"].binding_token(pay)
    w["psp"].payout_attestation(pay, w["p"], w["acct"], beta.digest)
    with pytest.raises(ValueError):
        w["psp"].payout_attestation(pay, w["p"], w["evil_acct"], beta.digest)
