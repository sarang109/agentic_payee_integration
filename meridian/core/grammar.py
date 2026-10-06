"""Route grammar (F2).

    R = ID+ (AG | SUB | CUS | ASG)* ID_term

read from the anchored brand to the terminal account, with side conditions:
  * SUB may follow only an AG or SUB edge whose delegate flag is set;
  * ASG replaces the current principal with the assignee;
  * the final ID edge must bind the terminal account to the current principal.

The checker is a finite automaton over edge types plus a principal register,
so a route of k edges costs O(k).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .edges import AG, ASG, CUS, ID, SUB, Edge
from .ids import L1, L4, layer

S_START, S_IDS, S_CHAIN, S_TERM = 0, 1, 2, 3


@dataclass
class GrammarResult:
    ok: bool
    principal: Optional[str]
    state: int
    reason: str = ""


def run(edges: Sequence[Edge], require_terminal: bool = False, start_principal: Optional[str] = None) -> GrammarResult:
    state = S_START if start_principal is None else S_CHAIN
    principal = start_principal
    prev: Optional[Edge] = None
    for i, e in enumerate(edges):
        if state == S_TERM:
            return GrammarResult(False, principal, state, f"edge after terminal binding at {i}")
        if e.etype == ID:
            if layer(e.dst) == L4:
                if principal is None:
                    return GrammarResult(False, principal, state, "terminal binding before principal")
                if e.src != principal:
                    return GrammarResult(False, principal, state, "terminal subject discontinuity")
                state = S_TERM
            elif state in (S_START, S_IDS):
                state = S_IDS
                if layer(e.dst) == L1:
                    principal = e.dst
            else:
                return GrammarResult(False, principal, state, "identity edge after delegation")
        elif e.etype in (AG, CUS):
            if state not in (S_IDS, S_CHAIN) or principal is None:
                return GrammarResult(False, principal, state, f"{e.etype} before principal")
            if e.subject is not None and e.subject != principal:
                return GrammarResult(False, principal, state, "edge collects for a different principal")
            state = S_CHAIN
        elif e.etype == SUB:
            if state != S_CHAIN or prev is None or prev.etype not in (AG, SUB) or not prev.delegate:
                return GrammarResult(False, principal, state, "SUB without delegate flag upstream")
            if e.subject is not None and e.subject != principal:
                return GrammarResult(False, principal, state, "edge collects for a different principal")
            state = S_CHAIN
        elif e.etype == ASG:
            if state not in (S_IDS, S_CHAIN) or layer(e.dst) != L1:
                return GrammarResult(False, principal, state, "assignment must name an entity")
            principal = e.dst
            state = S_CHAIN
        else:
            return GrammarResult(False, principal, state, f"unknown edge type {e.etype}")
        prev = e
    if require_terminal and state != S_TERM:
        return GrammarResult(False, principal, state, "missing terminal binding")
    if state == S_START:
        return GrammarResult(False, principal, state, "empty route")
    return GrammarResult(True, principal, state)
