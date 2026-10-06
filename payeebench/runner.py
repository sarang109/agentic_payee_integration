"""Chronological executor and deterministic judges.

All world events (edge issuance logged to the MTL, payout-configuration
changes, split-view forks, payments) run in time order. Each payment is
evaluated under every configuration on the same world state. Judges compare
the realised terminal account with ground truth; no LLM is involved.
"""

from __future__ import annotations

import random
from dataclasses import asdict
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from meridian.cba import CBA, CBAParams, Embedder
from meridian.core.decision import ALLOW, DENY, STEP_UP
from meridian.core.policy import Policy
from meridian.log import LogVerifier
from meridian.rws import SchedulerParams, load_profiles

from .cases import GENERATORS, PV_GENERATORS, AttackerKit, Case, gen_benign
from .configs import ALL_CONFIGS, Ctx, evaluate
from .world import DAY, World

_EMBEDDER: Optional[Embedder] = None


def shared_embedder() -> Embedder:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = Embedder()
    return _EMBEDDER


def build_bench(seed: int = 7, n_attack: int = 60, n_benign: int = 90, n_pv: int = 20,
                delta: int = 3 * DAY, attacks: Iterable[str] = tuple(GENERATORS), pvs: Iterable[str] = tuple(PV_GENERATORS),
                monitor_median_s: float = 6 * 3600, monitor_sigma: float = 1.0) -> Tuple[World, List[Case]]:
    world = World(seed=seed, delta=delta, monitor_median_s=monitor_median_s, monitor_sigma=monitor_sigma).build()
    rng = random.Random(seed * 1000 + 17)
    kit = AttackerKit(world, rng)
    cases = gen_benign(world, rng, n_benign)
    for a in attacks:
        cases += GENERATORS[a](world, kit, rng, n_attack)
    for pv in pvs:
        cases += PV_GENERATORS[pv](world, kit, rng, n_pv)
    return world, cases


def judge(world: World, case: Case, verdict: str, undone: bool) -> Dict:
    legit = world.legit_terminals(case.intended, case.payment.tuple)
    executed = verdict == ALLOW or (verdict == STEP_UP and case.user_confirms_stepup)
    lands_legit = case.exec_terminal in legit
    diverted = executed and not lands_legit
    return {
        "executed": executed,
        "lands_legit_if_paid": lands_legit,
        "diverted": diverted,
        "loss": diverted and not undone,
        "false_block": (not case.is_attack) and (verdict == DENY or (executed and undone)),
        "step_up": verdict == STEP_UP,
        "stepup_would_divert": verdict == STEP_UP and not lands_legit,
    }


def run(world: World, cases: List[Case], configs: Iterable[str] = ALL_CONFIGS, delta: Optional[int] = None,
        rho: int = 300, gossip: bool = True, probation_cap: int = 0, sched: Optional[SchedulerParams] = None,
        cba_params: Optional[CBAParams] = None, seed: int = 0, require_acceptance: bool = True,
        use_scope_meet: bool = True, progress: bool = False, hook=None) -> List[Dict]:
    """``hook(case, ctx, outcomes)`` runs after the configurations for each
    payment, in time order, and may return extra fields for the records."""
    configs = list(configs)
    delta = world.delta if delta is None else delta
    policy = Policy(rho=rho, require_acceptance=require_acceptance, use_scope_meet=use_scope_meet)
    log_verifier = LogVerifier(world.log, delta, world.gossip if gossip else None)
    ctx = Ctx(world, CBA(world.registry, cba_params or CBAParams(), shared_embedder()), policy, log_verifier,
              load_profiles(), sched or SchedulerParams(), probation_cap=probation_cap,
              rng=np.random.default_rng(seed), use_gossip=gossip)

    events: List[Tuple[int, int, str, object]] = []
    for (t, kind, obj) in world.log_events:
        events.append((t, 0, kind, obj))
    for c in cases:
        if c.log_view:
            events.append((c.fork_at, 1, "fork", c))
        events.append((c.payment.t, 2, "pay", c))
    events.sort(key=lambda e: (e[0], e[1]))

    records: List[Dict] = []
    n_pay = sum(1 for e in events if e[2] == "pay")
    done = 0
    for (t, _, kind, obj) in events:
        if kind == "edge":
            world.log.log_edge(obj, t)
        elif kind == "payout":
            world.log.log_payout_config(obj[0], obj[1], obj[2], t)
        elif kind == "fork":
            c: Case = obj
            world.flush_monitors(t)
            prev = world.log.sth(t, "main")
            world.log.equivocate(c.log_view)
            for (tf, e) in c.fork_edges:
                world.log.log_edge(e, tf, views=[c.log_view])
            victim = LogVerifier(world.log, delta, None if (c.no_gossip or not gossip) else world.gossip,
                                 view=c.log_view)
            victim.prev = prev
            ctx.victims[c.log_view] = victim
        else:
            c = obj
            world.flush_monitors(t)
            world.gossip.publish(world.log.sth(t, "main"))
            outs = {}
            for cfg in configs:
                out = evaluate(c, ctx, cfg)
                outs[cfg] = out
                j = judge(world, c, out.verdict, out.undone)
                rec = {
                    "case_id": c.case_id, "kind": c.kind, "variant": c.variant, "structure": c.structure,
                    "rail": c.rail, "premise_violation": c.premise_violation, "config": cfg,
                    "intended": c.intended, "impersonated": c.intended in world.impersonated,
                    "verdict": out.verdict, "stage": out.stage, "reasons": ";".join(out.reasons[:3]),
                    "level": out.level, "mode": out.mode, "undone": out.undone, "detected": out.detected,
                    "breach_certificate": out.breach, "detect_reason": out.detect_reason,
                    "decision_ms": round(out.decision_ms, 4), "sig_checks": out.sig_checks,
                    "amount": c.payment.amount, "t": c.payment.t, **j,
                }
                records.append(rec)
            if hook is not None:
                extra = hook(c, ctx, outs) or {}
                for r in records[-len(configs):]:
                    r.update(extra)
            done += 1
            if progress and done % 250 == 0:
                print(f"  {done}/{n_pay} payments")
    return records
