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


def connected_account(st: Stripe, label: str) -> dict:
    now = int(time.time())
    return st.post("/accounts", {
        "type": "custom", "country": "US", "email": f"{label}@example.com", "business_type": "individual",
        "capabilities[transfers][requested]": "true", "capabilities[card_payments][requested]": "true",
        "tos_acceptance[date]": now, "tos_acceptance[ip]": "127.0.0.1",
        "individual[first_name]": "Jenny", "individual[last_name]": "Rosen", "individual[email]": f"{label}@example.com",
        "individual[phone]": "0000000000", "individual[dob][day]": 1, "individual[dob][month]": 1,
        "individual[dob][year]": 1901, "individual[ssn_last_4]": "0000",
        "individual[address][line1]": "address_full_match", "individual[address][city]": "San Francisco",
        "individual[address][state]": "CA", "individual[address][postal_code]": "94111",
        "business_profile[mcc]": "5734", "business_profile[url]": "https://accessible.stripe.com",
        "external_account": "btok_us_verified", "metadata[meridian]": label,
    })


def default_bank_fingerprint(st: Stripe, acct: str) -> str:
    ext = st.get(f"/accounts/{acct}/external_accounts", {"object": "bank_account", "limit": 10})
    for b in ext["data"]:
        if b.get("default_for_currency"):
            return b["fingerprint"]
    return ext["data"][0]["fingerprint"]


def run_connect() -> Dict:
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key.startswith("sk_test_"):
        out = {"status": "skipped: no Stripe test key"}
        write_json("stripe_connect_summary", out)
        return out
    st = Stripe(key)
    try:
        brand = connected_account(st, "meridian-brand")
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
        rows.append({"case": "X3 payout-account change", "committed destination": f"bank fingerprint {bound}",
                     "observed destination": f"bank fingerprint {attested}",
                     "deviation detected": attested != bound, "breach certificate verifies": None,
                     "transfer reversed": None, "observe_s": None, "reversal_s": None,
                     "verifier decision": "DENY (terminal subject discontinuity)" if attested != bound else "ALLOW"})
    df = pd.DataFrame(rows)
    write_csv("stripe_connect_runs", df)
    write_table("stripe_connect", df, "X2/X3 reproduced on Stripe Connect test mode", index=False)
    out = {"status": "ok", "rows": rows}
    write_json("stripe_connect_summary", out)
    return out


if __name__ == "__main__":
    print(run_connect())
