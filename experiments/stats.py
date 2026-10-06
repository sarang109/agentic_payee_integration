"""Statistics plan (fixed before E2-E6 run).

* constructed attack cases: exact counts, no intervals;
* sampled / measured values: Wilson score intervals;
* clustered data: cluster bootstrap by merchant topology;
* paired configuration comparisons: exact McNemar (two-sided binomial on the
  discordant pairs).
"""

from __future__ import annotations

import math
from typing import Callable, Dict, Sequence, Tuple

import numpy as np
from scipy import stats as sps


def wilson(k: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(a_only: int, b_only: int) -> float:
    """Two-sided exact McNemar p-value from discordant counts."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    return float(min(1.0, sps.binomtest(min(a_only, b_only), n, 0.5, alternative="two-sided").pvalue))


def paired_mcnemar(x: Sequence[bool], y: Sequence[bool]) -> Dict[str, float]:
    x = np.asarray(x, bool)
    y = np.asarray(y, bool)
    a_only = int(np.sum(x & ~y))
    b_only = int(np.sum(~x & y))
    return {"x_only": a_only, "y_only": b_only, "p_value": mcnemar_exact(a_only, b_only)}


def cluster_bootstrap(values: Sequence[float], clusters: Sequence[str], stat: Callable[[np.ndarray], float] = np.mean,
                      n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> Tuple[float, float, float]:
    v = np.asarray(values, float)
    c = np.asarray(clusters)
    ids, inv = np.unique(c, return_inverse=True)
    groups = [v[inv == i] for i in range(len(ids))]
    rng = np.random.default_rng(seed)
    point = float(stat(v)) if len(v) else float("nan")
    if len(groups) < 2:
        return point, float("nan"), float("nan")
    boots = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(groups), len(groups))
        boots.append(stat(np.concatenate([groups[i] for i in pick])))
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    return point, float(lo), float(hi)


def fmt_rate(k: int, n: int, interval: bool = True) -> str:
    if n == 0:
        return "n/a"
    if not interval:
        return f"{k}/{n}"
    lo, hi = wilson(k, n)
    return f"{k / n:.3f} [{lo:.3f}, {hi:.3f}]"
