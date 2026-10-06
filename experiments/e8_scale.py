"""E8 scalability.

(a) PAV throughput for RAPs of k = 2..6 edges (real Ed25519 signatures);
(b) directory search (V1a, Lemma 1 scope filter) on synthetic layered graphs
    up to 1M identifiers and 10M edges, numpy CSR with vectorised scope
    filtering and a depth bound;
(c) Merkle log: build time, proof generation / verification and proof size.
"""

from __future__ import annotations

import math
import time
from typing import Dict, List

import numpy as np
import pandas as pd

from meridian.core.decision import Payment
from meridian.core.edges import AG, ID, SUB
from meridian.core.keys import KeyPair
from meridian.core.pav import RAP, BindingToken, pav
from meridian.core.policy import (BANK, DOMAIN_VERIFIER, PLATFORM, PSP, Policy, RoleCredential, TrustStore)
from meridian.core.scope import Scope
from meridian.core.status import StatusRegistry
from meridian.issuers import QVI, DomainVerifier, Platform, PSPOperator, make_entity
from meridian.log.merkle import MerkleTree, leaf_hash, root_of_hashes, verify_inclusion

from .common import QUICK, SEED, Timer, write_csv, write_json, write_table


# ------------------------------------------------------------------ (a) PAV

def _chain(k: int):
    """A valid RAP of exactly k edges: brand -> lei -> mor -> proc -> proc ..."""
    sr = StatusRegistry()
    trust = TrustStore()
    dv, qvi = DomainVerifier("dv", sr), QVI("qvi", sr)
    plat = Platform("plat", sr)
    for i in (dv, qvi, plat):
        i.register(trust)
    ent = make_entity("Brand Inc", "5493001KJTIIGC8Y1R12")
    trust.add_role_credential(qvi.role_credential(ent, 10**9))
    dns = {}
    dns["_meridian-challenge.brand.com"] = [dv.challenge("brand.com", ent.rep)]
    edges = [dv.bind("brand.com", ent, dns, 0, 10**9)]
    sc = Scope.make(rails={"card"})
    node = ent.lei_id
    if k >= 2:
        store = plat.new_account("store", ns="mor:plat")
        edges.append(plat.issue(AG, node, store, sc, 0, 10**9, plat.key, delegate=True, signing_key=ent.rep))
        node = store
    if k >= 3:
        main = "proc:plat/main"
        edges.append(plat.issue(AG, node, main, sc, 0, 10**9, plat.key, delegate=True))
        node = main
    while len(edges) < k:
        nxt = plat.new_account("seller")
        edges.append(plat.issue(SUB, node, nxt, sc, 0, 10**9, plat.key, delegate=True, subject=ent.lei_id))
        node = nxt
    pay = Payment("p1", node, "card", "USD", 1000, "5661", "US", 1000, "cart", "n1")
    beta = BindingToken.issue(plat.key if k >= 2 else ent.rep, pay)
    status = {e.status.list_id: sr.lists[e.status.list_id].snapshot(1000) for e in edges}
    return RAP(edges, status, beta), pay, trust


def pav_throughput(n: int) -> List[Dict]:
    rows = []
    for k in range(2, 7):
        rap, pay, trust = _chain(k)
        pol = Policy()
        d = pav(rap, pay, "brand:brand.com", pol, trust)
        assert d.allowed, (k, d.reasons)
        t0 = time.perf_counter()
        for _ in range(n):
            pav(rap, pay, "brand:brand.com", pol, trust)
        dt = time.perf_counter() - t0
        rows.append({"k_edges": k, "signature_checks": d.sig_checks, "pav_per_s": round(n / dt, 1),
                     "us_per_pav": round(dt / n * 1e6, 1), "rap_bytes": rap.wire_size()})
    return rows


# ------------------------------------------------------------------ (b) directory

class CSRGraph:
    def __init__(self, n_nodes: int, src: np.ndarray, dst: np.ndarray, rails: np.ndarray, cur: np.ndarray,
                 mcc: np.ndarray, geo: np.ndarray, ceil: np.ndarray, nbf: np.ndarray, exp: np.ndarray):
        order = np.argsort(src, kind="stable")
        self.dst = dst[order]
        self.rails, self.cur, self.mcc, self.geo = rails[order], cur[order], mcc[order], geo[order]
        self.ceil, self.nbf, self.exp = ceil[order], nbf[order], exp[order]
        self.indptr = np.zeros(n_nodes + 1, dtype=np.int64)
        np.add.at(self.indptr, src + 1, 1)
        np.cumsum(self.indptr, out=self.indptr)

    def reach(self, root: int, target: int, rail_bit: int, cur_bit: int, mcc_bit: int, geo_bit: int, amount: int,
              t: int, d_max: int = 6) -> bool:
        frontier = np.array([root], dtype=np.int64)
        seen = {root}
        for _ in range(d_max):
            if not len(frontier):
                return False
            starts, ends = self.indptr[frontier], self.indptr[frontier + 1]
            idx = np.concatenate([np.arange(s, e) for s, e in zip(starts, ends)]) if len(frontier) > 1 else \
                np.arange(starts[0], ends[0])
            if not len(idx):
                return False
            ok = ((self.rails[idx] >> rail_bit) & 1).astype(bool) & ((self.cur[idx] >> cur_bit) & 1).astype(bool) \
                & ((self.mcc[idx] >> np.uint64(mcc_bit)) & np.uint64(1)).astype(bool) \
                & ((self.geo[idx] >> np.uint64(geo_bit)) & np.uint64(1)).astype(bool) \
                & (self.ceil[idx] >= amount) & (self.nbf[idx] <= t) & (self.exp[idx] >= t)
            nxt = self.dst[idx[ok]]
            if (nxt == target).any():
                return True
            nxt = np.unique(nxt)
            nxt = nxt[[n not in seen for n in nxt]] if len(nxt) < 4096 else nxt
            seen.update(nxt.tolist())
            frontier = nxt
        return False


def synthetic_graph(n_nodes: int, n_edges: int, rng: np.random.Generator) -> Dict:
    """Layered graph: brands (L0) -> entities (L1) -> stores (L2) -> processing
    accounts (L3) -> settlement (L4), with marketplace hubs of heavy in-degree."""
    share = np.array([0.2, 0.2, 0.25, 0.2, 0.15])
    sizes = (share * n_nodes).astype(int)
    offs = np.concatenate([[0], np.cumsum(sizes)])
    layers = [np.arange(offs[i], offs[i + 1]) for i in range(5)]
    per = (np.array([0.12, 0.33, 0.33, 0.22]) * n_edges).astype(int)
    srcs, dsts = [], []
    for li, m in enumerate(per):
        s = rng.choice(layers[li], m)
        if li == 2:
            hubs = layers[3][: max(1, len(layers[3]) // 1000)]  # marketplace collection accounts
            d = np.where(rng.random(m) < 0.3, rng.choice(hubs, m), rng.choice(layers[3], m))
        else:
            d = rng.choice(layers[li + 1], m)
        srcs.append(s)
        dsts.append(d)
    src = np.concatenate(srcs).astype(np.int64)
    dst = np.concatenate(dsts).astype(np.int64)
    E = len(src)
    rails = np.where(rng.random(E) < 0.9, 0xFF, 1 << rng.integers(0, 6, E)).astype(np.uint8)
    cur = np.where(rng.random(E) < 0.8, 0xFFFFFFFF, 1 << rng.integers(0, 32, E)).astype(np.uint32)
    mcc = np.where(rng.random(E) < 0.7, np.uint64(0xFFFFFFFFFFFFFFFF),
                   np.left_shift(np.uint64(1), rng.integers(0, 64, E).astype(np.uint64))).astype(np.uint64)
    geo = np.where(rng.random(E) < 0.8, np.uint64(0xFFFFFFFFFFFFFFFF),
                   np.left_shift(np.uint64(1), rng.integers(0, 64, E).astype(np.uint64))).astype(np.uint64)
    ceil = rng.integers(10_000, 10_000_000, E).astype(np.int64)
    nbf = rng.integers(0, 1000, E).astype(np.int32)
    exp = rng.integers(10_000, 20_000, E).astype(np.int32)
    return {"layers": layers, "args": (n_nodes, src, dst, rails, cur, mcc, geo, ceil, nbf, exp)}


def directory_bench(sizes, rng, q: int) -> List[Dict]:
    rows = []
    for n_nodes, n_edges in sizes:
        with Timer(f"E8 graph {n_nodes:,} nodes / {n_edges:,} edges"):
            g = synthetic_graph(n_nodes, n_edges, rng)
            t0 = time.perf_counter()
            csr = CSRGraph(*g["args"])
            build_s = time.perf_counter() - t0
            lat = []
            hits = 0
            brands, procs = g["layers"][0], g["layers"][3]
            for qi in range(q):
                root = int(rng.choice(brands))
                target = int(rng.choice(procs))
                if qi % 2 == 0:
                    # half the queries ask for a node reached by a random walk
                    node, steps = root, 0
                    while steps < 3 and csr.indptr[node + 1] > csr.indptr[node]:
                        node = int(csr.dst[rng.integers(csr.indptr[node], csr.indptr[node + 1])])
                        steps += 1
                    target = node
                t0 = time.perf_counter()
                hits += csr.reach(root, target, 0, 0, 3, 0, 5000, 5000)
                lat.append((time.perf_counter() - t0) * 1000)
            mem = sum(a.nbytes for a in (csr.dst, csr.rails, csr.cur, csr.mcc, csr.geo, csr.ceil, csr.nbf, csr.exp,
                                         csr.indptr))
        rows.append({"nodes": n_nodes, "edges": len(g["args"][1]), "csr_build_s": round(build_s, 2),
                     "memory_MB": round(mem / 2**20, 1), "query_p50_ms": round(float(np.median(lat)), 3),
                     "query_p95_ms": round(float(np.quantile(lat, 0.95)), 3), "queries": q,
                     "reachable_share": round(hits / q, 3)})
        del g, csr
    return rows


# ------------------------------------------------------------------ (c) log

def path_len(index: int, size: int) -> int:
    n, m, length = size, index, 0
    while n > 1:
        k = 1 << (n - 1).bit_length() - 1
        if m < k:
            n = k
        else:
            m, n = m - k, n - k
        length += 1
    return length


def log_bench(sizes) -> List[Dict]:
    rows = []
    for n in sizes:
        hashes = [leaf_hash(i.to_bytes(8, "big")) for i in range(n)]
        t0 = time.perf_counter()
        root = root_of_hashes(hashes)
        root_s = time.perf_counter() - t0
        row = {"leaves": n, "root_build_s": round(root_s, 2),
               "inclusion_proof_bytes_max": 32 * max(path_len(0, n), path_len(n - 1, n)),
               "inclusion_proof_bytes_mean": float(round(32 * np.mean([path_len(i, n) for i in range(0, n, max(1, n // 1000))]), 1))}
        if n <= 2**20:
            tree = MerkleTree(hashes)
            t0 = time.perf_counter()
            assert tree.root() == root
            gen, ver = [], []
            for i in np.linspace(0, n - 1, 200).astype(int):
                a = time.perf_counter()
                pr = tree.inclusion_proof(int(i))
                b = time.perf_counter()
                assert verify_inclusion(hashes[i], int(i), n, pr, root)
                gen.append((b - a) * 1e3)
                ver.append((time.perf_counter() - b) * 1e3)
            cons = tree.consistency_proof(n // 2, n)
            row.update({"proof_gen_ms_p50": round(float(np.median(gen)), 3),
                        "proof_verify_ms_p50": round(float(np.median(ver)), 3),
                        "consistency_proof_bytes(n/2->n)": 32 * len(cons)})
        rows.append(row)
        del hashes
    return rows


def run_e8() -> dict:
    rng = np.random.default_rng(SEED)
    with Timer("E8 PAV throughput"):
        pav_rows = pav_throughput(300 if QUICK else 3000)
    write_table("e8_pav", pd.DataFrame(pav_rows), "E8: PAV cost by path length (single core)", index=False)
    sizes = [(10_000, 100_000), (100_000, 1_000_000)] if QUICK else \
        [(10_000, 100_000), (100_000, 1_000_000), (1_000_000, 10_000_000)]
    drows = directory_bench(sizes, rng, 100 if QUICK else 300)
    write_table("e8_directory", pd.DataFrame(drows), "E8: directory reachability with scope filtering (V1a)", index=False)
    lsizes = [2**14, 2**17] if QUICK else [2**14, 2**17, 2**20, 10_000_000]
    with Timer("E8 Merkle log"):
        lrows = log_bench(lsizes)
    write_table("e8_log", pd.DataFrame(lrows), "E8: Merchant Transparency Log proofs", index=False)
    out = {"pav": pav_rows, "directory": drows, "log": lrows}
    write_json("e8_summary", out)
    return out


if __name__ == "__main__":
    print(run_e8())
