"""x402 'exact' scheme on an EVM-style ledger, with MERIDIAN in the payment
requirements and an escrow wrapper for the ESCROW scheduling mode.

The payer signs a real EIP-3009 TransferWithAuthorization (EIP-712 typed
data) with eth-account. Settlement runs on ``LocalChain``, an in-process
ledger with ERC-20 balances, EIP-3009 nonce tracking, 2 s blocks and an
escrow contract. A public testnet can replace it by implementing the same
``settle`` interface; the experiments record which backend was used.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from eth_account import Account
from eth_account.messages import encode_typed_data

NETWORK = "eip155:84532"  # Base Sepolia identifier, used for the typed-data domain
CHAIN_ID = 84532
USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

TYPES = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ]
}


def domain(asset: str = USDC) -> dict:
    return {"name": "USDC", "version": "2", "chainId": CHAIN_ID, "verifyingContract": asset}


def payment_requirements(pay_to: str, amount: int, resource: str, meridian: Optional[dict] = None,
                         timeout: int = 60) -> dict:
    extra = {"name": "USDC", "version": "2"}
    if meridian is not None:
        extra["meridian"] = meridian
    return {"scheme": "exact", "network": NETWORK, "maxAmountRequired": str(amount), "resource": resource,
            "description": "agent purchase", "mimeType": "application/json", "payTo": pay_to,
            "maxTimeoutSeconds": timeout, "asset": USDC, "extra": extra}


def sign_payment(payer: "Account", req: dict, now: int, to: Optional[str] = None) -> str:
    auth = {"from": payer.address, "to": to or req["payTo"], "value": int(req["maxAmountRequired"]),
            "validAfter": now - 5, "validBefore": now + int(req["maxTimeoutSeconds"]),
            "nonce": "0x" + os.urandom(32).hex()}
    msg = encode_typed_data(domain(req["asset"]), TYPES, auth)
    sig = Account.sign_message(msg, payer.key).signature.hex()
    payload = {"x402Version": 1, "scheme": "exact", "network": req["network"],
               "payload": {"signature": sig if sig.startswith("0x") else "0x" + sig,
                           "authorization": {**auth, "value": str(auth["value"]),
                                             "validAfter": str(auth["validAfter"]),
                                             "validBefore": str(auth["validBefore"])}}}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def decode_header(header: str) -> dict:
    return json.loads(base64.b64decode(header))


@dataclass
class Escrow:
    payer: str
    payee: str
    amount: int
    deadline: float
    arbiter: str
    state: str = "held"  # held | released | refunded


@dataclass
class LocalChain:
    balances: Dict[str, int] = field(default_factory=dict)
    used_nonces: set = field(default_factory=set)
    escrows: Dict[str, Escrow] = field(default_factory=dict)
    receipts: List[dict] = field(default_factory=list)
    block_time: float = 2.0
    escrow_address: str = "0x" + "e5" * 20

    def mint(self, addr: str, amount: int) -> None:
        self.balances[addr.lower()] = self.balances.get(addr.lower(), 0) + amount

    def balance(self, addr: str) -> int:
        return self.balances.get(addr.lower(), 0)

    def _transfer(self, a: str, b: str, v: int) -> None:
        if self.balance(a) < v:
            raise ValueError("insufficient balance")
        self.balances[a.lower()] -= v
        self.mint(b, v)

    def verify(self, header: str, req: dict, now: int) -> Tuple[bool, str]:
        p = decode_header(header)
        auth = p["payload"]["authorization"]
        typed = {**auth, "value": int(auth["value"]), "validAfter": int(auth["validAfter"]),
                 "validBefore": int(auth["validBefore"])}
        try:
            signer = Account.recover_message(encode_typed_data(domain(req["asset"]), TYPES, typed),
                                             signature=p["payload"]["signature"])
        except Exception:
            return False, "signature"
        if signer.lower() != auth["from"].lower():
            return False, "signer"
        if int(auth["value"]) != int(req["maxAmountRequired"]):
            return False, "value"
        if not int(auth["validAfter"]) <= now <= int(auth["validBefore"]):
            return False, "validity"
        if auth["nonce"] in self.used_nonces:
            return False, "nonce-reused"
        if self.balance(auth["from"]) < int(auth["value"]):
            return False, "balance"
        return True, ""

    def settle(self, header: str, req: dict, now: int, escrow_terms: Optional[dict] = None) -> dict:
        ok, why = self.verify(header, req, now)
        if not ok:
            raise ValueError(why)
        auth = decode_header(header)["payload"]["authorization"]
        self.used_nonces.add(auth["nonce"])
        v = int(auth["value"])
        block_t = now + self.block_time
        if escrow_terms is not None:
            if auth["to"].lower() != self.escrow_address.lower():
                raise ValueError("escrow requires payment to the escrow contract")
            self._transfer(auth["from"], self.escrow_address, v)
            pid = escrow_terms["payment_id"]
            self.escrows[pid] = Escrow(auth["from"], escrow_terms["payee"], v, block_t + escrow_terms["window"],
                                       escrow_terms["arbiter"])
        else:
            self._transfer(auth["from"], auth["to"], v)
        rec = {"tx": "0x" + os.urandom(32).hex(), "from": auth["from"], "to": auth["to"], "value": v,
               "block_time": block_t, "escrow": escrow_terms is not None}
        self.receipts.append(rec)
        return rec

    def refund(self, pid: str, by: str, now: float) -> bool:
        e = self.escrows.get(pid)
        if e is None or e.state != "held" or by.lower() != e.arbiter.lower() or now > e.deadline:
            return False
        self._transfer(self.escrow_address, e.payer, e.amount)
        e.state = "refunded"
        return True

    def release_due(self, now: float) -> int:
        n = 0
        for pid, e in self.escrows.items():
            if e.state == "held" and now >= e.deadline:
                self._transfer(self.escrow_address, e.payee, e.amount)
                e.state = "released"
                n += 1
        return n
