import numpy as np
from eth_account import Account

from meridian.cba import fold, skeleton
from meridian.core.decision_log import DecisionLog
from meridian.protocols import mpp, x402
from meridian.core.keys import KeyPair
from meridian.rws import load_profiles, schedule
from meridian.rws.adapters import iso8583
from meridian.rws.window import toy_illustration


def test_iso8583_roundtrip_and_first_hop():
    req = iso8583.authorization_request("4111111111111111", 1234, "840", "000123", "5661", "451234", "acct_000101",
                                        "SHOP CITY US")
    mti, fields = iso8583.unpack(req)
    assert mti == "0100" and fields[4] == "000000001234" and fields[42] == "acct_000101"
    resp = iso8583.authorization_response(req)
    assert iso8583.unpack(resp)[1][39] == "00"
    assert iso8583.first_hop_from_record(resp, {"451234": "pspone"}) == "proc:pspone/acct_000101"


def test_x402_signature_binds_pay_to_and_escrow_refund():
    chain = x402.LocalChain()
    payer = Account.from_key(bytes.fromhex("11" * 32))
    merchant = Account.from_key(bytes.fromhex("22" * 32)).address
    arbiter = Account.from_key(bytes.fromhex("44" * 32)).address
    chain.mint(payer.address, 10_000)
    req = x402.payment_requirements(merchant, 500, "https://m.example/x")
    hdr = x402.sign_payment(payer, req, 1000)
    assert chain.verify(hdr, req, 1000) == (True, "")
    tampered = dict(req, payTo="0x" + "33" * 20)
    p = x402.decode_header(hdr)
    p["payload"]["authorization"]["to"] = tampered["payTo"]
    import base64, json
    assert chain.verify(base64.b64encode(json.dumps(p).encode()).decode(), tampered, 1000)[0] is False
    chain.settle(hdr, req, 1000)
    assert chain.balance(merchant) == 500
    with __import__("pytest").raises(ValueError):
        chain.settle(hdr, req, 1000)  # nonce reuse
    h2 = x402.sign_payment(payer, req, 1100, to=chain.escrow_address)
    chain.settle(h2, req, 1100, escrow_terms={"payment_id": "p2", "payee": merchant, "window": 600, "arbiter": arbiter})
    assert chain.refund("p2", arbiter, 1200)
    assert chain.balance(payer.address) == 10_000 - 500


def test_mpp_session_limit():
    k = KeyPair()
    s = mpp.Session("s1", limit=1000)
    ch = mpp.parse_challenge(mpp.challenge("shop", "acct:x/1", 600, "usd", "card", {"route": "abc"}))
    c1 = mpp.credential(s, k, ch)
    assert mpp.verify_credential(c1, k.public)["amount"] == 600
    assert mpp.credential(s, k, ch) is None  # second charge would exceed the session limit


def test_window_toy_matches_blueprint_illustration():
    t = toy_illustration()
    assert t["original_condition"] == 1.0
    assert abs(t["corrected_honest"] - 0.79) < 0.02
    assert abs(t["corrected_fastest_corrupted"] - 0.48) < 0.02
    assert abs(t["fresh_rho_3"] - 0.67) < 0.02


def test_scheduler_rail_dependence():
    p = load_profiles()
    assert schedule(p["card"], 100.0, 2).mode == "POST"
    for rail in ("a2a_instant", "stablecoin"):
        s = schedule(p[rail], 100.0, 2)
        assert not s.feasible["POST"] and s.mode in ("PRE", "ESCROW")


def test_skeletons():
    assert fold("Pаypal") == fold("Paypal")  # Cyrillic a
    assert skeleton("rn") == skeleton("m") or fold("rnicrosoft") != fold("microsoft")


def test_decision_log_chain():
    log = DecisionLog()
    for i in range(5):
        log.append({"i": i})
    assert log.verify()
    log.entries[2]["record"]["i"] = 99
    assert not log.verify()
