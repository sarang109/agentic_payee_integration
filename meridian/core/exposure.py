"""Funded routes (F6): exposure-capped admission and the hold-time threshold.

A custodian that holds a payer's funds for ``hold`` periods can steal what it
holds. The verifier cannot stop that before authorization (Theorem 1) and,
on the card rail, no post-authorization mode undoes it (E6), so the deviation
is attributable (Theorem 2) but not deterred. F6 makes it unprofitable by
bounding what a custodian holds relative to what it would lose.

Model (discrete time, one period per decision, discount factor ``beta``):

* honest operation earns ``margin`` per period; the franchise is worth
  ``V = margin / (1 - beta)``;
* a custodian holding exposure ``X`` may steal it once. With probability
  ``q`` the theft is detected: the franchise is lost from the next period and
  the bond is slashed after the hold time (to pay the victims). With
  probability ``1 - q`` it goes unnoticed and the custodian carries on;
* by the one-shot deviation principle, honest operation is optimal iff

      (1 - q) * X  <=  margin + q * beta * V + q * beta**hold * bond.

``q`` is a per-custodian detection probability. It cannot be measured in the
sandbox, so every use takes it as an input and the experiment sweeps it.

Admission rule: admit a payment of amount ``a`` to custodian ``c`` iff the
custodian's in-flight exposure after the payment stays within

      cap(c, q_hat) = min(deterrence_cap(c, q_hat), bond)

the first term keeps deviation unprofitable at the assumed detection
probability ``q_hat``, the second keeps the bond large enough to cover
everything held (coverage, which matters for a compromised custodian that
does not respond to incentives). The rule deters a rational custodian only
if the true ``q`` is at least ``q_hat``.

Not modelled: correlated detection, custodians that can leave with their
bond, repeated or partial theft, and the cost of the bond to the custodian.
Coalitions are handled in ``coalition_rational`` under the assumption that
colluders withhold the evidence that would detect them.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

INF = math.inf
# A custodian exactly at its cap is indifferent and is treated as honest;
# the relative tolerance keeps floating-point rounding from deciding that.
TOL = 1e-9


@dataclass(frozen=True)
class Custodian:
    name: str
    bond: float
    margin: float  # profit per period from honest operation
    beta: float  # discount factor per period, in (0, 1)
    hold: float  # periods the funds are held before onward release

    def __post_init__(self) -> None:
        if not (0.0 < self.beta < 1.0):
            raise ValueError("beta must be in (0, 1)")
        if self.bond < 0 or self.margin < 0 or self.hold < 0:
            raise ValueError("bond, margin and hold must be non-negative")

    @property
    def franchise(self) -> float:
        return self.margin / (1.0 - self.beta)


def _check_q(q: float) -> None:
    if not (0.0 <= q <= 1.0):
        raise ValueError("detection probability must be in [0, 1]")


def deviation_cost(c: Custodian, q: float) -> float:
    """What a theft costs in expectation, measured against honest operation:
    the margin forgone now, plus the franchise and the discounted bond if
    detected."""
    _check_q(q)
    return c.margin + q * (c.beta * c.franchise + (c.beta ** c.hold) * c.bond)


def rational_to_deviate(c: Custodian, exposure: float, q: float) -> bool:
    return (1.0 - q) * exposure > deviation_cost(c, q) * (1.0 + TOL)


def deterrence_cap(c: Custodian, q: float) -> float:
    """Largest exposure for which deviation is not strictly profitable."""
    _check_q(q)
    if q >= 1.0:
        return INF
    return deviation_cost(c, q) / (1.0 - q)


def deviation_threshold(c: Custodian, q: float) -> float:
    """Exposure above which ``rational_to_deviate`` is true."""
    return deterrence_cap(c, q) * (1.0 + TOL)


def admission_cap(c: Custodian, q_hat: float) -> float:
    return min(deterrence_cap(c, q_hat), c.bond)


def hold_time_threshold(c: Custodian, exposure: float, q: float) -> Optional[float]:
    """Longest hold time (periods) for which holding ``exposure`` is not worth
    stealing, given the custodian's bond, margin and discount factor
    (``c.hold`` is ignored).

    Returns ``inf`` when no hold time makes theft profitable (the exposure is
    already covered by margin and franchise alone) and ``None`` when even
    immediate release is not enough: the bond is too small to deter at this
    exposure and detection probability."""
    _check_q(q)
    slack = (1.0 - q) * exposure - c.margin - q * c.beta * c.franchise
    if slack <= 0.0:
        return INF
    if q == 0.0 or c.bond == 0.0:
        return None
    need = slack / (q * c.bond)  # required value of beta**T
    if need > 1.0:
        return None
    return math.log(need) / math.log(c.beta)


def required_bond(margin: float, beta: float, hold: float, q: float, target_cap: float) -> float:
    """Smallest bond for which ``admission_cap`` equals ``target_cap``: the
    bond must cover the exposure and deter at detection probability ``q``."""
    _check_q(q)
    if target_cap < 0:
        raise ValueError("target_cap must be non-negative")
    if q >= 1.0:
        return target_cap
    V = margin / (1.0 - beta)
    slack = (1.0 - q) * target_cap - margin - q * beta * V
    if slack <= 0.0:
        return target_cap
    if q == 0.0:
        return INF
    return max(target_cap, slack / (q * beta ** hold))


# ------------------------------------------------------------------ coalitions

def coalition_detection(honest_detection: Sequence[float], external: float = 0.0) -> float:
    """Probability a deviation by a coalition is detected when it withholds the
    evidence its own members would give: only the remaining honest custodians
    on the route (each detecting with its own probability) and an external
    channel (terminal bank, payer complaint) can expose it."""
    miss = 1.0 - external
    for q in honest_detection:
        _check_q(q)
        miss *= 1.0 - q
    return 1.0 - miss


def per_hop_detection(q_single: float, route_length: int, external: float = 0.0) -> float:
    """Detection probability contributed by each other hop on the route, given
    that a single custodian deviating alone is detected with probability
    ``q_single`` (the number the admission rule assumes). Solves
    ``1 - (1 - external) * (1 - p) ** (route_length - 1) = q_single``; returns
    0 when ``q_single`` is already explained by the external channel."""
    _check_q(q_single)
    _check_q(external)
    if route_length < 2:
        raise ValueError("a route needs at least two custodians for per-hop detection")
    if q_single <= external:
        return 0.0
    if external >= 1.0:
        return 0.0
    return 1.0 - ((1.0 - q_single) / (1.0 - external)) ** (1.0 / (route_length - 1))


def coalition_q(q_single: float, route_length: int, size: int, external: float = 0.0) -> float:
    """Detection probability when ``size`` custodians on a route of
    ``route_length`` collude and withhold their own evidence. ``size == 1``
    gives back ``q_single``."""
    if not (1 <= size <= route_length):
        raise ValueError("coalition size must be between 1 and the route length")
    p = per_hop_detection(q_single, route_length, external)
    return coalition_detection([p] * (route_length - size), external)


def coalition_rational(members: Sequence[Custodian], exposures: Sequence[float], q_coalition: float) -> bool:
    """Joint deviation is worth it iff the members' summed net payoffs are
    positive at the coalition's (lower) detection probability. Side payments
    are free, so the test is on the sum."""
    if len(members) != len(exposures):
        raise ValueError("one exposure per member")
    gain = sum((1.0 - q_coalition) * x for x in exposures)
    cost = sum(deviation_cost(m, q_coalition) for m in members)
    return gain > cost * (1.0 + TOL)


# ------------------------------------------------------------------ admission

@dataclass
class Admission:
    admitted: bool
    exposure_before: float
    cap: float
    reason: str = ""


@dataclass
class _Ledger:
    held: List[Tuple[float, float]] = field(default_factory=list)  # (release time, amount)
    total: float = 0.0


class FundedRoutes:
    """Admission control over a set of custodians.

    ``q_hat`` is the detection probability the verifier assumes: one number
    for all custodians or a per-custodian mapping. Exposure is the amount
    currently held (admitted and not yet released onward)."""

    def __init__(self, custodians: Sequence[Custodian], q_hat: float | Mapping[str, float]) -> None:
        self.custodians: Dict[str, Custodian] = {c.name: c for c in custodians}
        if len(self.custodians) != len(custodians):
            raise ValueError("duplicate custodian name")
        self._q = q_hat
        self._ledger: Dict[str, _Ledger] = {n: _Ledger() for n in self.custodians}

    def q_hat(self, name: str) -> float:
        q = self._q[name] if isinstance(self._q, Mapping) else self._q
        _check_q(q)
        return q

    def cap(self, name: str) -> float:
        return admission_cap(self.custodians[name], self.q_hat(name))

    def exposure(self, name: str, t: float) -> float:
        led = self._ledger[name]
        while led.held and led.held[0][0] <= t:
            _, amt = heapq.heappop(led.held)
            led.total -= amt
        if not led.held:
            led.total = 0.0  # no float drift once everything is released
        return led.total

    def admit(self, name: str, amount: float, t: float) -> Admission:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        before = self.exposure(name, t)
        cap = self.cap(name)
        if before + amount > cap:
            return Admission(False, before, cap, "exceeds-cap")
        led = self._ledger[name]
        heapq.heappush(led.held, (t + self.custodians[name].hold, amount))
        led.total += amount
        return Admission(True, before, cap)
