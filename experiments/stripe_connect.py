"""X2 and X3 on Stripe Connect test mode (separate charges and transfers).

X2  seller substitution at a custodial marketplace: the platform charges the
    buyer, has committed to transfer to the brand's connected account, and
    transfers to another connected account. The Stripe Transfer object is
    the G3 observation; the commitment plus the platform's signed transfer
    record form a breach certificate, and the transfer is reversed.
X3  payout-account change at the processor: the brand's connected account
    gets a new default external bank account; the payout-destination
    attestation (bank account fingerprint) no longer matches the account the
    bank bound to the brand at onboarding, so the route is denied.

Needs STRIPE_SECRET_KEY=sk_test_... on an account with Connect enabled
(Dashboard, test mode: Connect > Get started). Without Connect the step
records why it was skipped.
"""

from __future__ import annotations

import os
import time
from typing import Dict, Optional

import pandas as pd
import requests

from meridian.core.decision import Payment
from meridian.core.discharge import BreachCertificate, TransferRecord, verify_certificate
from meridian.core.keys import KeyPair
from meridian.core.policy import PLATFORM, TrustStore
from meridian.core.routes import REMIT, Commitment

from .common import Timer, write_csv, write_json, write_table

API = "https://api.stripe.com/v1"


class Stripe:
    def __init__(self, key: str) -> None:
        if not key.startswith("sk_test_"):
            raise RuntimeError("test-mode key required")
        self.s = requests.Session()
        self.s.auth = (key, "")

    def post(self, path: str, data: Optional[dict] = None) -> dict:
        r = self.s.post(f"{API}{path}", data=data or {}, timeout=60)
        out = r.json()
        if "error" in out:
            raise RuntimeError(out["error"].get("message", "stripe error"))
        return out

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        out = self.s.get(f"{API}{path}", params=params or {}, timeout=60).json()
        if "error" in out:
            raise RuntimeError(out["error"].get("message", "stripe error"))
        return out


V2_VERSION = "2026-09-30.endive"


def connected_account(st: Stripe, label: str) -> dict:
    """A platform-managed recipient account (Accounts v2) that can receive
    transfers, filled with Stripe's documented test identity values."""
    import json

    h = {"Authorization": f"Bearer {st.s.auth[0]}", "Stripe-Version": V2_VERSION, "Content-Type": "application/json"}
    body = {
        "contact_email": f"{label}@example.com", "display_name": label, "dashboard": "none",
        "identity": {
            "country": "us", "entity_type": "individual",
            "individual": {"given_name": "Jenny", "surname": "Rosen", "email": f"{label}@example.com",
                           "phone": "+14155550100", "date_of_birth": {"day": 1, "month": 1, "year": 1901},
                           "id_numbers": [{"type": "us_ssn_last_4", "value": "0000"}],
                           "address": {"country": "us", "line1": "address_full_match", "city": "San Francisco",
                                       "state": "CA", "postal_code": "94111"}},
            "attestations": {"terms_of_service": {"account": {
                "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ip": "127.0.0.1"}}}},
        "configuration": {"recipient": {"capabilities": {"stripe_balance": {"stripe_transfers": {"requested": True}}}}},
        "defaults": {"currency": "usd", "profile": {"business_url": "https://accessible.stripe.com"},
                     "responsibilities": {"fees_collector": "application", "losses_collector": "application"}},
        "metadata": {"meridian": label},
    }
    r = st.s.post("https://api.stripe.com/v2/core/accounts", headers=h, data=json.dumps(body), timeout=60).json()
    if "error" in r:
        raise RuntimeError(r["error"].get("message", "account creation failed"))
    acct = r["id"]
    st.post(f"/accounts/{acct}/external_accounts", {"external_account": "btok_us_verified"})
    for _ in range(20):
        g = st.s.get(f"https://api.stripe.com/v2/core/accounts/{acct}", headers=h,
                     params={"include": ["configuration.recipient"]}, timeout=60).json()
        status = g["configuration"]["recipient"]["capabilities"]["stripe_balance"]["stripe_transfers"]["status"]
        if status == "active":
            break
        time.sleep(1.5)
    return {"id": acct, "transfers": status}


def default_bank_fingerprint(st: Stripe, acct: str) -> str:
    ext = st.get(f"/accounts/{acct}/external_accounts", {"object": "bank_account", "limit": 10})
    for b in ext["data"]:
        if b.get("default_for_currency"):
            return b["fingerprint"]
    return ext["data"][0]["fingerprint"]


def _short(x: str) -> str:
    """Published tables keep only the last characters of Stripe object ids."""
    return x if len(x) < 10 else f"...{x[-6:]}"


def x3_decision(bound_fp: str, attested_fp: str):
    """Run the v2-core verifier on X3: the brand's bank bound the onboarding
    payout account (identified by Stripe's bank fingerprint) to the brand's
    entity; the processor now attests the current default payout account."""
    from meridian.core.edges import AG
    from meridian.core.pav import RAP
    from meridian.core.policy import Policy
    from meridian.core.routes import RouteBundle, verify_route
    from meridian.core.scope import Scope
    from meridian.core.status import StatusRegistry
    from meridian.issuers import QVI, Bank, DomainVerifier, PSPOperator, make_entity

    sr, trust = StatusRegistry(), TrustStore()
    dv, qvi, psp, bank = DomainVerifier("dv", sr), QVI("qvi", sr), PSPOperator("stripe", sr), Bank("stripebank", sr)
    for i in (dv, qvi, psp, bank):
        i.register(trust)
    brand = make_entity("Meridian Brand Inc", "5493001KJTIIGC8Y1R12")
    other = make_entity("Unknown Payee LLC", "5493009ZZTIIGC8Y1R99")
    for e in (brand, other):
        trust.add_role_credential(qvi.role_credential(e, 10**10))
    t = int(time.time())
    dns = {"_meridian-challenge.meridian-brand.example": [dv.challenge("meridian-brand.example", brand.rep)]}
    e0 = dv.bind("meridian-brand.example", brand, dns, t - 86400, t + 86400 * 365)
    p = psp.new_account()
    e1 = psp.issue(AG, brand.lei_id, p, Scope.make(rails={"card"}), t - 86400, t + 86400 * 365, psp.key,
                   signing_key=brand.rep)
    bound_acct = bank.open_account(brand, iban=bound_fp)
    # the new payout account is not the brand's: the bank binds it to whoever holds it
    new_acct = bank.open_account(brand if attested_fp == bound_fp else other, iban=attested_fp)
    term = bank.terminal_binding(new_acct, t - 3600, t + 86400 * 365)
    pay = Payment("x3", p, "card", "USD", 4200, "5734", "US", t, "cart-x3", "n-x3")
    beta = psp.binding_token(pay)
    snaps = {e.status.list_id: sr.lists[e.status.list_id].snapshot(t) for e in (e0, e1, term)}
    bundle = RouteBundle(RAP([e0, e1], snaps, beta), [], [psp.payout_attestation(pay, p, new_acct, beta.digest)],
                         term, snaps)
    _ = bound_acct
    return verify_route(bundle, pay, "brand:meridian-brand.example", Policy(), trust)


def run_connect() -> Dict:
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key.startswith("sk_test_"):
        out = {"status": "skipped: no Stripe test key"}
        write_json("stripe_connect_summary", out)
        return out
    st = Stripe(key)
    try:
        brand = connected_account(st, "meridian-brand")
        if brand["transfers"] != "active":
            raise RuntimeError(f"transfers capability is {brand['transfers']}")
    except RuntimeError as e:
        out = {"status": f"skipped: {e}"[:300]}
        write_json("stripe_connect_summary", out)
        write_table("stripe_connect", pd.DataFrame([out]), "X2/X3 on Stripe Connect test mode", index=False)
        return out
    rows = []
    platform_key = KeyPair()  # the marketplace's signing key for commitments and transfer records
    trust = TrustStore()
    trust.add_root(platform_key, PLATFORM, {"proc:stripe-platform"}, "platform")
    with Timer("X2/X3 on Stripe Connect test mode"):
        fake = connected_account(st, "meridian-fake-seller")
        # X2: charge on the platform, committed to the brand, transferred elsewhere
        pi = st.post("/payment_intents", {"amount": 4200, "currency": "usd", "payment_method": "pm_card_bypassPending",
                                          "payment_method_types[]": "card", "confirm": "true",
                                          "transfer_group": "meridian-x2"})
        charge = pi["latest_charge"]
        pay = Payment(pi["id"], "proc:stripe-platform/main", "card", "USD", 4200, "5734", "US", int(time.time()),
                      "cart-x2", "n-x2")
        commit = Commitment.issue(platform_key, REMIT, pay, "proc:stripe-platform/main", f"proc:stripe/{brand['id']}",
                                  "beta-x2")
        t0 = time.perf_counter()
        tr = st.post("/transfers", {"amount": 4200, "currency": "usd", "destination": fake["id"],
                                    "source_transaction": charge, "transfer_group": "meridian-x2"})
        observed = st.get(f"/transfers/{tr['id']}")
        record = TransferRecord.issue(platform_key, pay.payment_id, "proc:stripe-platform/main",
                                      f"proc:stripe/{observed['destination']}", observed["amount"], int(time.time()))
        cert = BreachCertificate(commit, record)
        detect_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        rev = st.post(f"/transfers/{tr['id']}/reversals", {"amount": 4200})
        reversal_s = time.perf_counter() - t1
        rows.append({"case": "X2 seller substitution", "committed destination": brand["id"],
                     "observed destination": observed["destination"], "deviation detected": observed["destination"] != brand["id"],
                     "breach certificate verifies": verify_certificate(cert, trust),
                     "transfer reversed": rev.get("amount") == 4200, "observe_s": round(detect_s, 3),
                     "reversal_s": round(reversal_s, 3)})
        # X3: payout account changed after onboarding
        bound = default_bank_fingerprint(st, brand["id"])
        st.post(f"/accounts/{brand['id']}/external_accounts", {
            "external_account[object]": "bank_account", "external_account[country]": "US",
            "external_account[currency]": "usd", "external_account[routing_number]": "110000000",
            "external_account[account_number]": "000111111116", "default_for_currency": "true"})
        attested = default_bank_fingerprint(st, brand["id"])
        decision = x3_decision(bound, attested)
        rows.append({"case": "X3 payout-account change", "committed destination": f"bank fingerprint {_short(bound)}",
                     "observed destination": f"bank fingerprint {_short(attested)}",
                     "deviation detected": attested != bound, "breach certificate verifies": None,
                     "transfer reversed": None, "observe_s": None, "reversal_s": None,
                     "verifier decision": f"{decision.verdict} ({';'.join(decision.reasons[:1]) or 'G2'})"})
        rows[0]["committed destination"] = _short(rows[0]["committed destination"])
        rows[0]["observed destination"] = _short(rows[0]["observed destination"])
    df = pd.DataFrame(rows)
    write_csv("stripe_connect_runs", df)
    write_table("stripe_connect", df, "X2/X3 reproduced on Stripe Connect test mode", index=False)
    out = {"status": "ok", "rows": rows}
    write_json("stripe_connect_summary", out)
    return out


if __name__ == "__main__":
    print(run_connect())
