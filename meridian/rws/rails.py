"""Rail profiles: reversibility windows, observers and void behaviour.

All times are seconds after authorization. The defaults are modelling
assumptions (documented in config/rails.yaml with the reasoning for each);
E6 replaces the card void latency with measured values when Stripe test mode
keys are configured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml

from ..core.decision import G1, G3, G4
from .window import Sampler, WindowModel, constant, lognormal

_CONFIG = os.path.join(os.path.dirname(__file__), "..", "..", "config", "rails.yaml")


@dataclass
class ObserverSpec:
    name: str
    level: int
    latency: Sampler


@dataclass
class RailProfile:
    name: str
    window: Sampler
    observers: List[ObserverSpec]
    decision: Sampler
    void: Sampler
    void_success: float
    escrow_supported: bool = False
    escrow_window: float = 0.0
    escrow_latency: Sampler = field(default_factory=lambda: constant(0.0))
    onward_after_window: bool = True  # custodial transfers happen after capture/finality
    transfer_delay: Sampler = field(default_factory=lambda: constant(0.0))
    irreversible: bool = False

    def observers_at(self, level: int) -> List[ObserverSpec]:
        return [o for o in self.observers if o.level == level]

    def window_model(self, level: int, escrow: bool = False) -> WindowModel:
        obs = [o.latency for o in self.observers_at(level)]
        w = constant(self.escrow_window) if escrow else self.window
        return WindowModel(w, obs, self.decision, self.void if not escrow else constant(1.0),
                           self.void_success if not escrow else 0.999)


def _sampler(spec) -> Sampler:
    if isinstance(spec, (int, float)):
        return constant(float(spec))
    kind = spec.get("kind", "lognormal")
    if kind == "constant":
        return constant(float(spec["value"]))
    return lognormal(float(spec["median"]), float(spec.get("sigma", 0.5)))


def load_profiles(path: Optional[str] = None) -> Dict[str, RailProfile]:
    path = os.path.abspath(path or _CONFIG)
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    out = {}
    level_names = {"G1": G1, "G3": G3, "G4": G4}
    for name, r in cfg["rails"].items():
        out[name] = RailProfile(
            name=name,
            window=_sampler(r["window"]),
            observers=[ObserverSpec(o["name"], level_names[o["level"]], _sampler(o["latency"])) for o in r["observers"]],
            decision=_sampler(r["decision"]),
            void=_sampler(r["void"]),
            void_success=float(r["void_success"]),
            escrow_supported=bool(r.get("escrow_supported", False)),
            escrow_window=float(r.get("escrow_window", 0.0)),
            escrow_latency=_sampler(r.get("escrow_latency", 0.0)),
            onward_after_window=bool(r.get("onward_after_window", True)),
            transfer_delay=_sampler(r.get("transfer_delay", 0.0)),
            irreversible=bool(r.get("irreversible", False)),
        )
    return out
