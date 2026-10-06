"""Algorithm 4: Reversibility-Window Scheduler (RWS).

Among the feasible modes m in {PRE, POST, ESCROW, STEP-UP} pick

    m* = argmin_m  lambda * a * P_div(m) + c_lat(m) + c_ux(m)

where P_div(m) is the residual probability that a post-authorization
diversion is not undone. POST is feasible only when POST-safe_f(r) holds.
For instant transfers and stablecoins W_r ~ 0, so POST is infeasible and the
choice reduces to PRE or ESCROW.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, Optional, Tuple

from ..core.decision import G1, G2, G3, G4
from .rails import RailProfile
from .window import WindowModel, post_safe_prob

PRE, POST, ESCROW, STEP = "PRE", "POST", "ESCROW", "STEP-UP"


@dataclass
class SchedulerParams:
    f: int = 0
    eps: float = 0.01
    lam: float = 1.0
    p_post_g2: float = 0.002  # prior of post-authorization deviation after a G2 allow
    p_post_g1: float = 0.02   # ... after a G1-only allow
    escrow_cost_per_hour: float = 0.02  # friction units per hour of delayed funds
    stepup_cost: float = 2.0
    stepup_catch: float = 0.5
    n_mc: int = 40_000


@dataclass
class Schedule:
    mode: str
    feasible: Dict[str, bool]
    p_catch: Dict[str, float]
    cost: Dict[str, float]


_CATCH_CACHE: Dict[Tuple, float] = {}


def catch_prob(profile: RailProfile, mode: str, f: int, n: int) -> float:
    key = (profile.name, mode, f, n, profile.escrow_window, getattr(profile.void, "median", None))
    if key in _CATCH_CACHE:
        return _CATCH_CACHE[key]
    if mode == POST:
        # first-hop deviations are seen by G1 observers; use the fastest
        # observer class available on the rail
        level = G1 if profile.observers_at(G1) else min(o.level for o in profile.observers)
        p = post_safe_prob(profile.window_model(level), f=f, n=n)
    elif mode == ESCROW:
        obs = [o.latency for o in profile.observers]
        p = post_safe_prob(WindowModel(profile.window_model(G1, escrow=True).window, obs, profile.decision,
                                       profile.escrow_latency, 0.999), f=f, n=n)
    else:
        p = 0.0
    _CATCH_CACHE[key] = p
    return p


def schedule(profile: RailProfile, amount_major: float, level: int, params: Optional[SchedulerParams] = None) -> Schedule:
    p = params or SchedulerParams()
    prior = p.p_post_g2 if level >= G2 else p.p_post_g1
    catch = {PRE: 0.0, POST: catch_prob(profile, POST, p.f, p.n_mc),
             ESCROW: catch_prob(profile, ESCROW, p.f, p.n_mc) if profile.escrow_supported else 0.0,
             STEP: p.stepup_catch}
    feasible = {PRE: True, POST: catch[POST] >= 1 - p.eps, ESCROW: profile.escrow_supported, STEP: True}
    friction = {PRE: 0.0, POST: 0.0, ESCROW: p.escrow_cost_per_hour * profile.escrow_window / 3600.0 + 0.05,
                STEP: p.stepup_cost}
    cost = {m: p.lam * amount_major * prior * (1 - catch[m]) + friction[m] for m in catch if feasible[m]}
    best = min(cost, key=lambda m: (cost[m], [PRE, POST, ESCROW, STEP].index(m)))
    return Schedule(best, feasible, catch, cost)
