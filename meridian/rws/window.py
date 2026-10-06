"""Window theorem (F4, Theorem 3).

    POST-safe_f(r)  iff  Pr[delta_(f+1) + delta_d + delta_v <= W_r] * s_v >= 1 - eps
    FRESH-safe(r)   iff  rho = 0  or  Pr[rho + delta_d + delta_v <= W_r] * s_v >= 1 - eps

delta_(f+1) is the (f+1)-th smallest observer latency: the adversary corrupts
the fastest f observers. The original (v1) condition counted only the report:
Pr[min_o delta_o <= W_r].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Sequence

import numpy as np

Sampler = Callable[[np.random.Generator, int], np.ndarray]


def lognormal(median: float, sigma: float) -> Sampler:
    def f(rng: np.random.Generator, n: int) -> np.ndarray:
        if median <= 0:
            return np.zeros(n)
        return median * np.exp(rng.normal(0.0, sigma, n))

    f.median, f.sigma = median, sigma  # type: ignore[attr-defined]
    return f


def constant(value: float) -> Sampler:
    def f(rng: np.random.Generator, n: int) -> np.ndarray:
        return np.full(n, float(value))

    f.median, f.sigma = value, 0.0  # type: ignore[attr-defined]
    return f


def empirical(samples: Sequence[float]) -> Sampler:
    arr = np.asarray(samples, dtype=float)

    def f(rng: np.random.Generator, n: int) -> np.ndarray:
        return rng.choice(arr, size=n, replace=True)

    f.median, f.sigma = float(np.median(arr)), float("nan")  # type: ignore[attr-defined]
    return f


@dataclass
class WindowModel:
    window: Sampler
    observers: List[Sampler]
    decision: Sampler
    void: Sampler
    void_success: float


def order_stat(observers: Sequence[Sampler], k: int, rng: np.random.Generator, n: int) -> np.ndarray:
    """k-th smallest (1-based) of the observer latencies; inf if fewer."""
    if k > len(observers):
        return np.full(n, np.inf)
    mat = np.stack([o(rng, n) for o in observers], axis=1)
    mat.sort(axis=1)
    return mat[:, k - 1]


def post_safe_prob(m: WindowModel, f: int = 0, n: int = 200_000, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    d = order_stat(m.observers, f + 1, rng, n) + m.decision(rng, n) + m.void(rng, n)
    return float(np.mean(d <= m.window(rng, n)) * m.void_success)


def original_post_safe_prob(m: WindowModel, n: int = 200_000, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    return float(np.mean(order_stat(m.observers, 1, rng, n) <= m.window(rng, n)))


def fresh_safe_prob(m: WindowModel, rho: float, n: int = 200_000, seed: int = 0) -> float:
    if rho == 0:
        return 1.0
    rng = np.random.default_rng(seed)
    d = rho + m.decision(rng, n) + m.void(rng, n)
    return float(np.mean(d <= m.window(rng, n)) * m.void_success)


def post_safe(m: WindowModel, f: int, eps: float, **kw) -> bool:
    return post_safe_prob(m, f, **kw) >= 1 - eps


def fresh_safe(m: WindowModel, rho: float, eps: float, **kw) -> bool:
    return rho == 0 or fresh_safe_prob(m, rho, **kw) >= 1 - eps


def toy_illustration() -> dict:
    """The F4 toy case: window 10 units; observer medians 1 and 4; void median
    5; void success 0.97; decision median 0.25; lognormal spread 0.6."""
    s = 0.6
    m = WindowModel(constant(10), [lognormal(1, s), lognormal(4, s)], lognormal(0.25, s), lognormal(5, s), 0.97)
    return {
        "original_condition": original_post_safe_prob(m),
        "corrected_honest": post_safe_prob(m, f=0),
        "corrected_fastest_corrupted": post_safe_prob(m, f=1),
        "fresh_rho_3": fresh_safe_prob(m, rho=3),
        "parameters": {"window": 10, "observer_medians": [1, 4], "void_median": 5, "void_success": 0.97,
                       "decision_median": 0.25, "lognormal_sigma": s},
    }
