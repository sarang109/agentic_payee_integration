from hypothesis import given, settings
from hypothesis import strategies as st

from meridian.log.merkle import (MerkleTree, leaf_hash, root_of_hashes, verify_consistency, verify_inclusion)


@settings(max_examples=60, deadline=None)
@given(st.integers(min_value=1, max_value=300), st.data())
def test_inclusion_proofs_verify(n, data):
    t = MerkleTree()
    for i in range(n):
        t.append(i.to_bytes(4, "big"))
    i = data.draw(st.integers(min_value=0, max_value=n - 1))
    proof = t.inclusion_proof(i)
    assert verify_inclusion(t.leaves[i], i, n, proof, t.root())
    assert not verify_inclusion(leaf_hash(b"other"), i, n, proof, t.root())


@settings(max_examples=60, deadline=None)
@given(st.integers(min_value=1, max_value=300), st.data())
def test_consistency_proofs_verify(n, data):
    t = MerkleTree()
    for i in range(n):
        t.append(i.to_bytes(4, "big"))
    m = data.draw(st.integers(min_value=1, max_value=n))
    proof = t.consistency_proof(m, n)
    assert verify_consistency(m, n, t.root(m), t.root(n), proof)
    if m < n:
        forked = t.copy(m)
        forked.append(b"evil")
        for i in range(m + 1, n):
            forked.append(i.to_bytes(4, "big"))
        assert not verify_consistency(m, n, t.root(m), forked.root(), proof)


def test_iterative_root_matches():
    for n in (1, 2, 3, 5, 8, 13, 100, 1025):
        hs = [leaf_hash(i.to_bytes(4, "big")) for i in range(n)]
        assert root_of_hashes(hs) == MerkleTree(hs).root()
