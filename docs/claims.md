# Claims and where they are established

| Claim | Blueprint tag | Established by | Where |
|---|---|---|---|
| Hierarchy G0-G4; Theorem 1 (pre-authorization checks reach G2 at most, and only with all custodians committed) | [P] | Proof in the blueprint; X6 (no commitment) is held at G1 by the verifier | `meridian/core/routes.py` (`verify_route` returns G1 step-up), `experiments/toys.py` X6 |
| Route grammar, O(k) checker | [P] | Automaton implementation; F3 structures S1-S7 accepted; brute-force cross-check of the directory search | `meridian/core/grammar.py`, `tests/test_scope_directory.py` |
| Theorem 2 attributability (T11) | [P] | Tamarin `no_false_blame`, `executable_blame`; breach certificates in X5 and A13 | `formal/tamarin/meridian_g2.spthy`, `meridian/core/discharge.py`, E2 A13 |
| Committed-route soundness (T10) | [D] | Tamarin `committed_route_soundness`, `commitment_authentic`; F3 X2/X3 | `formal/tamarin/meridian_g2.spthy`, `experiments/toys.py` |
| Theorem 3 window inequality, FRESH-safe | [P] | Monte Carlo of both conditions per rail; toy illustration reproduced; E6 protocol-level runs | `meridian/rws/window.py`, `results/tables/f4_toy.md`, E6 |
| T8 impossibility of POST on W_r = 0 | [P] | E6: POST undoes nothing before finality on instant and stablecoin rails | `results/tables/e6_residual_loss_f0.md` |
| Proposition 4 split payments | [P]/[S] | Linear verifier vs exact search on exact-fit instances | `meridian/core/split.py`, `results/tables/f5_split.md` |
| Lemma 1 scope filter (T3) | short proof | Hypothesis property test of the meet; BFS vs brute-force enumerator | `tests/test_scope_directory.py` |
| T1 DF soundness | reduction + Tamarin | Tamarin `df_soundness` | `formal/tamarin/meridian_v1.spthy` |
| T2 unilateral-claim resistance | Tamarin | `unilateral_claim_resistance` (fails with -D=ONESIDED); ablation 1 | same, `results/tables/ablation1_bilateral.md` |
| T4 post-binding swap detection | Tamarin + mutation tests | `post_binding_swap` (fails with -D=NOBETA); AP2/ACP mutations | same, `results/tables/t4_mutations.md` |
| T5 visibility / equivocation detection | argument + simulation | MTL with split views and gossip; A10 vs PV4 | `meridian/log/mtl.py`, E2 |
| T6 anchoring bound | definition + measured | CBA margin rule; held-out false-commit with Wilson intervals | `meridian/cba/anchoring.py`, E4 |
| T7 detection before finality | proof + measured | E6 card first-hop voided under POST when POST-safe holds | E6 |
| T9 payee privacy | scheme properties + ProVerif | Groth16 membership hides scope and position; ProVerif equivalence of the k-anonymous lookup (and its failure with the full hash) | `zk/circuits/payee_membership.circom`, `formal/proverif/` |
| P10 / P18 for AP2 and ACP | Tamarin | `payee_authenticity`, `discovery_runtime_consistency` fail without the extension and hold with it | `formal/tamarin/checkout_ext.spthy` |

## Found while mechanizing

`no_false_blame` initially failed: an honest custodian asked twice for the
same payment id could sign two different commitments and then be blamed for
honestly executing one of them. Operators now refuse a second, different
commitment for the same payment (`Operator.commit`), and the verifier denies a
bundle with conflicting commitments from one custodian (`verify_route`).
