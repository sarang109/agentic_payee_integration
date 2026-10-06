"""Split payments under aggregate budgets (F5, Proposition 4).

Verifying a split plan that names a route per destination is linear in total
route length: check each route, then sum amounts per edge against the edge's
remaining budget. Finding a plan where n amounts must each pass through one of
m intermediaries with remaining budgets C_j contains bin packing, so the party
that knows the split must supply it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class SplitLeg:
    destination: str
    amount: int
    route: Tuple[str, ...]  # edge ids along the route


def verify_split(plan: Sequence[SplitLeg], budgets: Dict[str, int],
                 route_ok: Callable[[SplitLeg], bool] = lambda leg: True) -> Tuple[bool, str]:
    used: Dict[str, int] = {}
    for leg in plan:
        if not route_ok(leg):
            return False, f"route for {leg.destination}"
        for eid in leg.route:
            used[eid] = used.get(eid, 0) + leg.amount
    for eid, amt in used.items():
        if eid in budgets and amt > budgets[eid]:
            return False, f"budget exceeded on {eid}"
    return True, ""


def find_split(amounts: Sequence[int], capacities: Sequence[int], deadline_s: float = 30.0) -> Tuple[Optional[List[int]], int, bool]:
    """Exact search: assign each amount to one intermediary within capacity.
    Returns (assignment or None, nodes explored, timed_out)."""
    order = sorted(range(len(amounts)), key=lambda i: -amounts[i])
    remaining = list(capacities)
    assign = [-1] * len(amounts)
    nodes = 0
    t_end = time.perf_counter() + deadline_s
    timed_out = False

    def dfs(k: int) -> bool:
        nonlocal nodes, timed_out
        nodes += 1
        if nodes % 4096 == 0 and time.perf_counter() > t_end:
            timed_out = True
            return False
        if k == len(order):
            return True
        i = order[k]
        tried = set()
        for j in range(len(remaining)):
            if remaining[j] >= amounts[i] and remaining[j] not in tried:
                tried.add(remaining[j])
                remaining[j] -= amounts[i]
                assign[i] = j
                if dfs(k + 1):
                    return True
                remaining[j] += amounts[i]
                if timed_out:
                    return False
        return False

    ok = dfs(0)
    return (assign if ok else None), nodes, timed_out
