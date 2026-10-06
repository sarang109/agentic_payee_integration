"""Scope lattice (Definition 2).

A scope is (R, C, A, M, G): permitted rails, currencies, per-payment ceiling
(minor units), merchant category codes and geography. ``None`` in a set
position means "unrestricted" (the top element for that component). Scopes
compose along a path by meet, so a path is never broader than its narrowest
edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Optional

RAILS = ("card", "psp_token", "wallet", "a2a_instant", "stablecoin", "bnpl")

INF = 2**62


def _fs(values: Optional[Iterable[str]]) -> Optional[FrozenSet[str]]:
    return None if values is None else frozenset(values)


def _meet_set(a: Optional[FrozenSet[str]], b: Optional[FrozenSet[str]]) -> Optional[FrozenSet[str]]:
    if a is None:
        return b
    if b is None:
        return a
    return a & b


def _contains(s: Optional[FrozenSet[str]], v: str) -> bool:
    return s is None or v in s


@dataclass(frozen=True)
class PaymentTuple:
    rail: str
    currency: str
    amount: int
    mcc: str
    geo: str


@dataclass(frozen=True)
class Scope:
    rails: Optional[FrozenSet[str]] = None
    currencies: Optional[FrozenSet[str]] = None
    ceiling: int = INF
    mccs: Optional[FrozenSet[str]] = None
    geos: Optional[FrozenSet[str]] = None

    @classmethod
    def make(cls, rails=None, currencies=None, ceiling=INF, mccs=None, geos=None) -> "Scope":
        return cls(_fs(rails), _fs(currencies), int(ceiling), _fs(mccs), _fs(geos))

    @classmethod
    def top(cls) -> "Scope":
        return cls()

    def meet(self, other: "Scope") -> "Scope":
        return Scope(
            _meet_set(self.rails, other.rails),
            _meet_set(self.currencies, other.currencies),
            min(self.ceiling, other.ceiling),
            _meet_set(self.mccs, other.mccs),
            _meet_set(self.geos, other.geos),
        )

    def contains(self, t: PaymentTuple) -> bool:
        return (
            _contains(self.rails, t.rail)
            and _contains(self.currencies, t.currency)
            and t.amount <= self.ceiling
            and _contains(self.mccs, t.mcc)
            and _contains(self.geos, t.geo)
        )

    def leq(self, other: "Scope") -> bool:
        """Partial order: self is at most as broad as other."""
        return self.meet(other) == self

    def is_empty(self) -> bool:
        return (
            (self.rails is not None and not self.rails)
            or (self.currencies is not None and not self.currencies)
            or self.ceiling < 0
            or (self.mccs is not None and not self.mccs)
            or (self.geos is not None and not self.geos)
        )

    def to_json(self) -> dict:
        def enc(s):
            return None if s is None else sorted(s)

        return {
            "R": enc(self.rails),
            "C": enc(self.currencies),
            "A": self.ceiling,
            "M": enc(self.mccs),
            "G": enc(self.geos),
        }

    @classmethod
    def from_json(cls, d: dict) -> "Scope":
        return cls.make(d.get("R"), d.get("C"), d.get("A", INF), d.get("M"), d.get("G"))


def meet_all(scopes: Iterable[Scope]) -> Scope:
    out = Scope.top()
    for s in scopes:
        out = out.meet(s)
    return out
