"""V1a: receiving-authority directory with scope-filtered reachability.

Lemma 1: with set-intersection and minimum-ceiling scopes a path's meet
contains the payment tuple exactly when every edge's scope does, so DF
reduces to reachability in the filtered graph G_t^pi. The search below runs
over the product of the filtered graph and the route-grammar automaton, so it
returns only paths PAV would also accept.

Lying modes (for E1 and ablation 6):
    "omit"   drop every path for a chosen set of payees
    "stale"  serve status snapshots older than the verifier's rho
    "forge"  return edges whose signatures do not verify
    "assert" answer "reachable" without evidence (only fools V1a-trusting)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .decision import ALLOW, DENY, G1, STEP_UP, Decision, Payment
from .edges import AG, ASG, CUS, ID, SUB, Edge
from .ids import L1, L4, layer
from .keys import SIG_CHECKS
from .pav import RAP, BindingToken, check_edges, verify_binding
from .policy import Policy, TrustStore
from .scope import PaymentTuple
from .status import StatusRegistry, StatusSnapshot

_START, _IDS, _CHAIN, _TERM = 0, 1, 2, 3


def _step(state: Tuple[int, bool, Optional[str]], e: Edge) -> Optional[Tuple[int, bool, Optional[str]]]:
    g, prev_deleg, principal = state
    if g == _TERM:
        return None
    if e.etype == ID:
        if layer(e.dst) == L4:
            if principal is None or e.src != principal:
                return None
            return (_TERM, False, principal)
        if g in (_START, _IDS):
            return (_IDS, False, e.dst if layer(e.dst) == L1 else principal)
        return None
    if e.etype in (AG, CUS):
        if g not in (_IDS, _CHAIN) or principal is None:
            return None
        if e.subject is not None and e.subject != principal:
            return None
        return (_CHAIN, e.delegate, principal)
    if e.etype == SUB:
        if g != _CHAIN or not prev_deleg:
            return None
        if e.subject is not None and e.subject != principal:
            return None
        return (_CHAIN, e.delegate, principal)
    if e.etype == ASG:
        if g not in (_IDS, _CHAIN) or layer(e.dst) != L1:
            return None
        return (_CHAIN, e.delegate, e.dst)
    return None


@dataclass
class Directory:
    status: StatusRegistry
    edges_by_src: Dict[str, List[Edge]] = field(default_factory=dict)
    edges_by_dst: Dict[str, List[Edge]] = field(default_factory=dict)
    lying: Optional[str] = None
    lie_targets: Set[str] = field(default_factory=set)
    rho_dir: int = 0
    queries: List[dict] = field(default_factory=list)

    def add(self, e: Edge) -> None:
        self.edges_by_src.setdefault(e.src, []).append(e)
        self.edges_by_dst.setdefault(e.dst, []).append(e)

    def add_all(self, edges: Iterable[Edge]) -> None:
        for e in edges:
            self.add(e)

    def _usable(self, e: Edge, t: PaymentTuple, now: int, trust: Optional[TrustStore]) -> bool:
        if not e.valid_at(now) or not e.scope.contains(t):
            return False
        if self.status.revoked_now(e.status, now - self.rho_dir):
            return False
        return True

    def find_path(self, src: str, dst: str, t: PaymentTuple, now: int, d_max: int) -> Optional[List[Edge]]:
        """BFS over (node, grammar state); first path found is shortest."""
        start = (src, (_START, False, None))
        prev: Dict[tuple, Tuple[tuple, Edge]] = {}
        seen = {start}
        q = deque([(start, 0)])
        while q:
            (node, st), depth = q.popleft()
            if node == dst and st[0] in (_IDS, _CHAIN, _TERM) and depth > 0:
                path = []
                cur = (node, st)
                while cur != start:
                    pcur, e = prev[cur]
                    path.append(e)
                    cur = pcur
                return list(reversed(path))
            if depth >= d_max:
                continue
            for e in self.edges_by_src.get(node, ()):
                if not self._usable(e, t, now, None):
                    continue
                nst = _step(st, e)
                if nst is None:
                    continue
                key = (e.dst, nst)
                if key in seen:
                    continue
                seen.add(key)
                prev[key] = ((node, st), e)
                q.append((key, depth + 1))
        return None

    def roots_reaching(self, dst: str, t: PaymentTuple, now: int, d_max: int) -> Set[str]:
        """Brands (L0 roots) with a filtered path to dst (reverse search, then
        a forward grammar check per candidate)."""
        cands: Set[str] = set()
        seen = {dst}
        q = deque([(dst, 0)])
        while q:
            node, depth = q.popleft()
            if layer(node) == 0:
                cands.add(node)
                continue
            if depth >= d_max:
                continue
            for e in self.edges_by_dst.get(node, ()):
                if e.src not in seen and self._usable(e, t, now, None):
                    seen.add(e.src)
                    q.append((e.src, depth + 1))
        return {b for b in cands if self.find_path(b, dst, t, now, d_max) is not None}

    def query(self, anchor: str, payee: str, t: PaymentTuple, now: int, d_max: int, rho_verifier: int) -> dict:
        self.queries.append({"anchor": anchor, "payee": payee, "amount": t.amount, "rail": t.rail, "t": now})
        if self.lying == "assert" and payee in self.lie_targets:
            return {"reachable": True, "edges": [], "status": {}, "others": []}
        path = None
        if not (self.lying == "omit" and payee in self.lie_targets):
            path = self.find_path(anchor, payee, t, now, d_max)
        others = [] if path else sorted(self.roots_reaching(payee, t, now, d_max) - {anchor})
        status: Dict[str, StatusSnapshot] = {}
        snap_time = now
        if self.lying == "stale" and payee in self.lie_targets:
            snap_time = max(0, now - rho_verifier - 3600)
        if path:
            for e in path:
                status[e.status.list_id] = self.status.lists[e.status.list_id].snapshot(snap_time)
        edges = list(path or [])
        if self.lying == "forge" and payee in self.lie_targets and edges:
            from dataclasses import replace
            edges = [replace(edges[0], sig_u=bytes(64))] + edges[1:]
        return {"reachable": path is not None, "edges": edges, "status": status, "others": others}


def v1a_verify(directory: Directory, payment: Payment, anchor: Optional[str], beta: Optional[BindingToken],
               policy: Policy, trust: TrustStore, trusting: bool = False, available: bool = True) -> Decision:
    """V1a decision. ``trusting`` models a client that believes the directory's
    yes/no answer without checking signatures (a weaker variant)."""
    start = SIG_CHECKS.value
    if not available:
        return Decision(STEP_UP, reasons=["directory-unavailable"], stage="v1a")
    if anchor is None:
        return Decision(STEP_UP, reasons=["no-anchor"], stage="v1a")
    ans = directory.query(anchor, payment.payee, payment.tuple, payment.t, policy.d_max, policy.rho)
    if trusting:
        if ans["reachable"]:
            return Decision(ALLOW, G1, [], anchor, stage="v1a-trusting")
        if ans["others"]:
            return Decision(DENY, reasons=["path-to-different-entity"], stage="v1a-trusting")
        return Decision(STEP_UP, reasons=["no-path"], stage="v1a-trusting")
    if not ans["reachable"] or not ans["edges"]:
        if ans["others"]:
            return Decision(DENY, reasons=["path-to-different-entity"], root=ans["others"][0],
                            sig_checks=SIG_CHECKS.value - start, stage="v1a")
        return Decision(STEP_UP, reasons=["no-path"], sig_checks=SIG_CHECKS.value - start, stage="v1a")
    edges = ans["edges"]
    pc = check_edges(edges, ans["status"], payment.tuple, payment.t, policy, trust)
    if not pc.ok:
        verdict = DENY if (pc.tamper and policy.deny_on_tamper) else STEP_UP
        return Decision(verdict, reasons=pc.reasons, sig_checks=SIG_CHECKS.value - start, stage="v1a")
    ok, why = verify_binding(beta, payment, edges[-1], trust)
    if not ok:
        verdict = DENY if policy.deny_on_tamper and why in ("beta-sig", "beta-mismatch") else STEP_UP
        return Decision(verdict, reasons=[why], sig_checks=SIG_CHECKS.value - start, stage="v1a")
    return Decision(ALLOW, G1, [], anchor, pc.principal, pc.scope, sig_checks=SIG_CHECKS.value - start, stage="v1a")


def rap_from_directory(ans: dict, beta: Optional[BindingToken]) -> RAP:
    return RAP(list(ans["edges"]), dict(ans["status"]), beta)
