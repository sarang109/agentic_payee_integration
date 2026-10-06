"""Simulated SEPA Instant Credit Transfer with a Verification-of-Payee
sandbox (EPC VoP scheme rulebook v1.1 response codes).

VoP runs before authorization: for MERIDIAN it is the terminal binding for
G2 (entity or LEI to account), never a receipt.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ...issuers.base import Bank

MTCH, CMTC, NMTC, NOAP = "MTCH", "CMTC", "NMTC", "NOAP"
_MAP = {"MATCH": MTCH, "CLOSE_MATCH": CMTC, "NO_MATCH": NMTC, "NOT_POSSIBLE": NOAP}


@dataclass
class VoPSandbox:
    banks: Dict[str, Bank]
    log: List[dict] = field(default_factory=list)

    def request(self, acct: str, party_name: Optional[str] = None, lei: Optional[str] = None) -> dict:
        t0 = time.perf_counter()
        bank_name = acct.split(":", 1)[1].split("/", 1)[0]
        bank = self.banks.get(bank_name)
        res = NOAP if bank is None else _MAP[bank.vop(acct, name=party_name, lei=lei)]
        out = {"matchResult": res}
        if res == CMTC and bank is not None:
            out["matchedName"] = bank.holder_names.get(acct)
        self.log.append({"acct": acct, "name": party_name, "lei": lei, "result": res,
                         "ms": (time.perf_counter() - t0) * 1000})
        return out


@dataclass
class InstantTransfer:
    rng: np.random.Generator
    settle_median_s: float = 3.0
    max_s: float = 10.0
    recall_success: float = 0.3

    def send(self, debtor: str, creditor_acct: str, amount: int, t: float) -> dict:
        lat = min(self.max_s, float(self.settle_median_s * np.exp(self.rng.normal(0, 0.4))))
        return {"msg": "pacs.008", "creditor": creditor_acct, "amount": amount, "accepted_at": t,
                "settled_at": t + lat, "irrevocable": True}

    def recall(self, transfer: dict) -> bool:
        """camt.056 recall: depends on the beneficiary bank and customer."""
        return bool(self.rng.random() < self.recall_success)
