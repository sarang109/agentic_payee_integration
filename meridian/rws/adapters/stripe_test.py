"""Stripe test mode (manual capture) for measuring authorization and void
latency on the card rail, plus a simulator with the same interface.

Live mode is used only when STRIPE_SECRET_KEY starts with ``sk_test_``; a
live-mode key is refused. Nothing here ever captures a real payment.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import requests

API = "https://api.stripe.com/v1"


class StripeTestMode:
    backend = "stripe-test-mode"

    def __init__(self, key: Optional[str] = None) -> None:
        key = key or os.environ.get("STRIPE_SECRET_KEY", "")
        if not key.startswith("sk_test_"):
            raise RuntimeError("a Stripe *test* secret key (sk_test_...) is required")
        self.s = requests.Session()
        self.s.auth = (key, "")

    def _post(self, path: str, data: dict) -> dict:
        r = self.s.post(f"{API}{path}", data=data, timeout=30)
        r.raise_for_status()
        return r.json()

    def authorize(self, amount: int, currency: str = "usd", metadata: Optional[dict] = None) -> Dict:
        t0 = time.perf_counter()
        data = {"amount": amount, "currency": currency, "payment_method": "pm_card_visa", "confirm": "true",
                "capture_method": "manual", "payment_method_types[]": "card"}
        for k, v in (metadata or {}).items():
            data[f"metadata[{k}]"] = v
        pi = self._post("/payment_intents", data)
        return {"id": pi["id"], "status": pi["status"], "latency_s": time.perf_counter() - t0}

    def void(self, pi_id: str) -> Dict:
        t0 = time.perf_counter()
        pi = self._post(f"/payment_intents/{pi_id}/cancel", {})
        return {"status": pi["status"], "latency_s": time.perf_counter() - t0, "ok": pi["status"] == "canceled"}


@dataclass
class StripeSimulator:
    """Same interface; latencies drawn from the card profile assumptions."""

    rng: np.random.Generator
    auth_median_s: float = 0.9
    void_median_s: float = 1.2
    void_success: float = 0.995
    backend: str = "simulator"
    intents: Dict[str, str] = field(default_factory=dict)

    def authorize(self, amount: int, currency: str = "usd", metadata: Optional[dict] = None) -> Dict:
        pid = f"pi_sim_{len(self.intents) + 1:08d}"
        self.intents[pid] = "requires_capture"
        return {"id": pid, "status": "requires_capture",
                "latency_s": float(self.auth_median_s * np.exp(self.rng.normal(0, 0.3)))}

    def void(self, pi_id: str) -> Dict:
        ok = bool(self.rng.random() < self.void_success)
        self.intents[pi_id] = "canceled" if ok else "requires_capture"
        return {"status": self.intents[pi_id], "ok": ok,
                "latency_s": float(self.void_median_s * np.exp(self.rng.normal(0, 0.4)))}


def card_backend(rng: np.random.Generator):
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if key.startswith("sk_test_"):
        return StripeTestMode(key)
    return StripeSimulator(rng)


def measure_void_latency(backend, n: int = 30, amount: int = 1234) -> List[Dict]:
    out = []
    for i in range(n):
        a = backend.authorize(amount, metadata={"meridian_run": "e6", "i": str(i)})
        v = backend.void(a["id"])
        out.append({"auth_s": a["latency_s"], "void_s": v["latency_s"], "void_ok": v["ok"], "backend": backend.backend})
    return out
