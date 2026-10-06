"""T3: scope-filter correctness (Lemma 1) against a brute-force path
enumerator, and lattice properties of the scope meet."""

import itertools
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from meridian.core.directory import Directory, _step
from meridian.core.scope import PaymentTuple, Scope
from payeebench.world import T_EXP_START, World

RAILS = ["card", "psp_token", "a2a_instant", "stablecoin"]
CURS = ["USD", "EUR", "GBP"]

scopes = st.builds(
    lambda r, c, a: Scope.make(rails=r, currencies=c, ceiling=a),
    st.one_of(st.none(), st.sets(st.sampled_from(RAILS), min_size=0, max_size=4)),
    st.one_of(st.none(), st.sets(st.sampled_from(CURS), min_size=0, max_size=3)),
    st.integers(min_value=0, max_value=10_000),
)
tuples = st.builds(lambda r, c, a: PaymentTuple(r, c, a, "5661", "US"), st.sampled_from(RAILS), st.sampled_from(CURS),
                   st.integers(min_value=0, max_value=10_000))


@settings(max_examples=200, deadline=None)
@given(st.lists(scopes, min_size=1, max_size=6), tuples)
def test_meet_contains_iff_each_contains(path, t):
    meet = Scope.top()
    for s in path:
        meet = meet.meet(s)
    assert meet.contains(t) == all(s.contains(t) for s in path)


@settings(max_examples=100, deadline=None)
@given(scopes, scopes, scopes)
def test_meet_is_a_semilattice(a, b, c):
    assert a.meet(b) == b.meet(a)
    assert a.meet(b).meet(c) == a.meet(b.meet(c))
    assert a.meet(a) == a
    assert a.meet(b).leq(a)


def _brute_reachable(directory, src, dst, t, now, d_max):
    """Enumerate every edge sequence up to d_max and apply the same grammar."""
    def rec(node, state, depth):
        if node == dst and depth > 0 and state[0] in (1, 2, 3):
            return True
        if depth == d_max:
            return False
        for e in directory.edges_by_src.get(node, ()):
            if not directory._usable(e, t, now, None):
                continue
            nst = _step(state, e)
            if nst is not None and rec(e.dst, nst, depth + 1):
                return True
        return False
    return rec(src, (0, False, None), 0)


def test_directory_matches_brute_force():
    world = World(seed=3, n_brands=40).build()
    directory = Directory(world.sr)
    from experiments.e1_v1a_v1b import all_edges
    directory.add_all(all_edges(world))
    rng = random.Random(0)
    brands = [b for b in world.brands if world.brands[b].structure != "S11"]
    payees = sorted({tpl.payee for b in world.brands.values() for tpl in b.templates})
    checked = 0
    for _ in range(300):
        b = rng.choice(brands)
        p = rng.choice(payees)
        t = PaymentTuple(rng.choice(["card", "psp_token", "a2a_instant", "stablecoin", "bnpl"]),
                         rng.choice(["USD", "EUR", "GBP", "USDC"]), rng.choice([100, 10_000, 1_000_000]),
                         world.brands[b].mcc, world.brands[b].geo)
        now = T_EXP_START
        fast = directory.find_path(b, p, t, now, 6) is not None
        assert fast == _brute_reachable(directory, b, p, t, now, 6)
        checked += fast
    assert checked > 0
