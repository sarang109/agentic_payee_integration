"""x402 on a public testnet (Base Sepolia, USDC, public x402 facilitator).

The payer signs the same EIP-3009 authorizations as on the local ledger
(meridian.protocols.x402.sign_payment) and the public facilitator verifies
and settles them on Base Sepolia. Three cases:

  honest      payTo is the merchant; verify, settle, and wait for the chain
              receipt (measured settlement and receipt latency, transaction
              hashes archived)
  tampered    the facilitator receives an authorization whose `to` was
              rewritten after signing; it must reject the signature
  mismatch    a correctly signed authorization to an attacker address is
              presented against requirements naming the merchant; it must
              be rejected because `to` differs from payTo

The escrow contract used by the ESCROW mode stays on the local ledger.

Runs when MERIDIAN_X402_KEY_FILE points to a funded Base Sepolia test key;
otherwise the archived run is reused, or the step reports why it skipped.
Test network and test USDC only.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Dict, List, Optional

import pandas as pd
import requests
from eth_account import Account

from meridian.protocols import x402

from .common import QUICK, RAW, Timer, write_csv, write_json, write_table
from .stats import fmt_rate

FACILITATOR = os.environ.get("MERIDIAN_X402_FACILITATOR", "https://x402.org/facilitator")
RPC = os.environ.get("MERIDIAN_BASE_SEPOLIA_RPC", "https://sepolia.base.org")
V1_NETWORK = "base-sepolia"
RUNS_CSV = os.path.join(RAW, "x402_testnet_runs.csv")
AMOUNT = 10_000  # 0.01 USDC (6 decimals)
# a fixed merchant address and a fixed attacker address (keys derived from labels, test use only)
MERCHANT = Account.from_key(bytes.fromhex(("6d65726368616e74" * 4))).address
ATTACKER = Account.from_key(bytes.fromhex(("61747461636b6572" * 4))).address


def _rpc(method: str, params: list) -> dict:
    r = requests.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=30)
    r.raise_for_status()
    return r.json()


def usdc_balance(addr: str) -> int:
    data = "0x70a08231" + addr[2:].lower().rjust(64, "0")
    return int(_rpc("eth_call", [{"to": x402.USDC, "data": data}, "latest"])["result"], 16)


def _v1(req: dict) -> dict:
    return dict(req, network=V1_NETWORK)


def _payload(header: str) -> dict:
    p = x402.decode_header(header)
    p["network"] = V1_NETWORK
    return p


def _post(path: str, payload: dict, req: dict) -> tuple:
    body = {"x402Version": 1, "paymentPayload": payload, "paymentRequirements": _v1(req)}
    t0 = time.perf_counter()
    r = requests.post(f"{FACILITATOR}/{path}", json=body, timeout=120)
    dt = time.perf_counter() - t0
    try:
        js = r.json()
    except ValueError:
        js = {"raw": r.text[:300]}
    return r.status_code, js, dt


def _wait_receipt(tx: str, timeout_s: float = 90) -> Optional[dict]:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        res = _rpc("eth_getTransactionReceipt", [tx]).get("result")
        if res:
            return res
        time.sleep(0.25)
    return None


def run_live(key: str, n_honest: int, n_bad: int) -> List[Dict]:
    payer = Account.from_key(key)
    rows: List[Dict] = []
    for i in range(n_honest):
        req = x402.payment_requirements(MERCHANT, AMOUNT, "https://merchant.example/item")
        hdr = x402.sign_payment(payer, req, int(time.time()))
        p = _payload(hdr)
        sv, jv, dv = _post("verify", p, req)
        t_settle = time.perf_counter()
        ss, js, ds = _post("settle", p, req)
        tx = js.get("transaction") or js.get("txHash") or ""
        rec = _wait_receipt(tx) if tx else None
        t_receipt = time.perf_counter() - t_settle
        rows.append({"case": "honest", "i": i, "verify_http": sv, "verify_valid": bool(jv.get("isValid")),
                     "verify_reason": jv.get("invalidReason", ""), "verify_s": round(dv, 3),
                     "settle_http": ss, "settle_success": bool(js.get("success")),
                     "settle_reason": js.get("errorReason", ""), "settle_s": round(ds, 3), "tx": tx,
                     "receipt_status": int(rec["status"], 16) if rec else None,
                     "block": int(rec["blockNumber"], 16) if rec else None,
                     "settle_to_receipt_s": round(t_receipt, 3) if rec else None})
    for i in range(n_bad):
        req = x402.payment_requirements(MERCHANT, AMOUNT, "https://merchant.example/item")
        hdr = x402.sign_payment(payer, req, int(time.time()))
        p = _payload(hdr)
        p["payload"]["authorization"]["to"] = ATTACKER
        sv, jv, dv = _post("verify", p, dict(req, payTo=ATTACKER))
        rows.append({"case": "tampered", "i": i, "verify_http": sv, "verify_valid": bool(jv.get("isValid")),
                     "verify_reason": jv.get("invalidReason", ""), "verify_s": round(dv, 3)})
        att_req = x402.payment_requirements(ATTACKER, AMOUNT, "https://merchant.example/item")
        hdr2 = x402.sign_payment(payer, att_req, int(time.time()))
        sv2, jv2, dv2 = _post("verify", _payload(hdr2), req)
        rows.append({"case": "mismatch", "i": i, "verify_http": sv2, "verify_valid": bool(jv2.get("isValid")),
                     "verify_reason": jv2.get("invalidReason", ""), "verify_s": round(dv2, 3)})
    return rows


def prev_meta() -> Dict:
    p = os.path.join(RAW, "x402_testnet_meta.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def balance_check(meta: Dict, before: int, after: int, rows: List[Dict]) -> Dict:
    """The payer's on-chain balance must drop by exactly the settled
    payments; otherwise a failed settlement moved funds."""
    settled = sum(1 for r in rows if r["case"] == "honest" and r.get("settle_success"))
    old = meta.get("balance_check", {})
    return {"start_usdc": old.get("start_usdc", before / 1e6), "after_usdc": after / 1e6,
            "settled_payments_all_runs": old.get("settled_payments_all_runs", 0) + settled,
            "this_run_drop_usdc": (before - after) / 1e6, "this_run_expected_drop_usdc": settled * AMOUNT / 1e6,
            "consistent": before - after == settled * AMOUNT and old.get("consistent", True),
            "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def run_x402_testnet() -> Dict:
    key_file = os.environ.get("MERIDIAN_X402_KEY_FILE", "")
    df: Optional[pd.DataFrame] = None
    source = ""
    prev = pd.read_csv(RUNS_CSV, keep_default_na=False) if os.path.exists(RUNS_CSV) else None
    if prev is not None and "run" not in prev.columns:
        prev["run"] = 1
        prev["run_utc"] = (json.load(open(os.path.join(RAW, "x402_testnet_meta.json"))).get("run_date_utc", "")
                           if os.path.exists(os.path.join(RAW, "x402_testnet_meta.json")) else "")
    if prev is not None and os.environ.get("MERIDIAN_X402_RERUN") != "1":
        df, source = prev, "archived"
    elif key_file and os.path.exists(key_file):
        with open(key_file) as fh:
            key = fh.read().strip()
        addr = Account.from_key(key).address
        bal = usdc_balance(addr)
        need = AMOUNT * (3 if QUICK else 20)
        if bal < need:
            return {"status": f"skipped: test wallet holds {bal / 1e6:.2f} USDC, needs {need / 1e6:.2f}"}
        with Timer("x402 on Base Sepolia via the public facilitator"):
            rows = run_live(key, 3 if QUICK else 20, 2 if QUICK else 10)
        time.sleep(5)
        bal_after = usdc_balance(addr)
        df, source = pd.DataFrame(rows), "live"
        # repeated runs are appended, never replaced
        df["run"] = (int(prev["run"].max()) + 1) if prev is not None else 1
        df["run_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if prev is not None:
            df = pd.concat([prev, df], ignore_index=True)
        write_csv("x402_testnet_runs", df)
        write_json("x402_testnet_meta", {"network": "Base Sepolia (eip155:84532)", "asset": x402.USDC,
                                         "facilitator": FACILITATOR, "payer": addr, "merchant": MERCHANT,
                                         "attacker": ATTACKER, "amount_units": AMOUNT,
                                         "run_date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                         "balance_check": balance_check(prev_meta(), bal, bal_after, rows)})
    if df is None:
        return {"status": "skipped: no funded test key (MERIDIAN_X402_KEY_FILE) and no archived run"}

    def b(frame, col):
        return frame[col].astype(str).str.lower().isin(["true", "1", "1.0"])

    out_rows = []
    groups = [(f"honest payment to merchant, run {int(r)} ({str(g.run_utc.iloc[0])[:16]})", g)
              for r, g in df[df.case == "honest"].groupby("run")] if "run" in df.columns else []
    if len(groups) > 1:
        groups.append(("honest payment to merchant, all runs", df[df.case == "honest"]))
    elif not groups:
        groups = [("honest payment to merchant", df[df.case == "honest"])]
    for label_h, hon in groups:
        settled = hon[b(hon, "settle_success")]
        fails = sorted({str(x).splitlines()[0][:80] for x in hon[~b(hon, "settle_success")].settle_reason})
        lat = pd.to_numeric(settled.settle_s, errors="coerce")
        rec = pd.to_numeric(settled.settle_to_receipt_s, errors="coerce")
        out_rows.append({"case": label_h, "runs": len(hon),
                         "facilitator verify accepted": fmt_rate(int(b(hon, "verify_valid").sum()), len(hon)),
                         "settled on chain": fmt_rate(len(settled), len(hon)),
                         "settle p50 / p95 s": f"{lat.median():.2f} / {lat.quantile(0.95):.2f}" if len(lat) else "-",
                         "settle to receipt p50 / p95 s": f"{rec.median():.2f} / {rec.quantile(0.95):.2f}"
                         if rec.notna().any() else "-",
                         "rejection reasons": ("settlement errors: " + "; ".join(fails)) if fails else ""})
    for case, label in (("tampered", "recipient rewritten after signing"),
                        ("mismatch", "signed to attacker, presented as merchant")):
        x = df[df.case == case]
        if len(x):
            out_rows.append({"case": label, "runs": len(x),
                             "facilitator verify accepted": fmt_rate(int(b(x, "verify_valid").sum()), len(x)),
                             "settled on chain": "-", "settle p50 / p95 s": "-", "settle to receipt p50 / p95 s": "-",
                             "rejection reasons": ", ".join(sorted(set(x.verify_reason.astype(str)) - {""}))})
    meta_p = os.path.join(RAW, "x402_testnet_meta.json")
    meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
    write_table("x402_testnet", pd.DataFrame(out_rows),
                "x402 exact payments on Base Sepolia through the public facilitator (measured on a public testnet)",
                f"All runs are kept, none are dropped. {_balance_text(meta)}Latest run {meta.get('run_date_utc', '?')}, test USDC {AMOUNT / 1e6} per payment. Transaction hashes are in "
                "results/raw/x402_testnet_runs.csv. The escrow wrapper used by the ESCROW mode runs on the local "
                "ledger only.", index=False)
    return {"status": "ok", "source": source, "rows": out_rows, "meta": meta}


def _balance_text(meta: Dict) -> str:
    bc = meta.get("balance_check")
    if not bc:
        return ""
    return (f"On-chain check: the payer held {bc['start_usdc']:.2f} test USDC before the first run and "
            f"{bc['after_usdc']:.2f} after the last, a drop of exactly {bc['settled_payments_all_runs']} settled "
            f"payments, so {'failed settlements moved no funds' if bc['consistent'] else 'THE BALANCE DOES NOT MATCH'}. ")


if __name__ == "__main__":
    print(run_x402_testnet())
