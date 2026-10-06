# MERIDIAN

Merchant-to-Endpoint Receiving-authority Integrity with Delegation, Intent
anchoring and Notarized receipts: a payer-side check that the party about to
receive an agent's payment is authorized to receive for the brand the user
meant, and that the money went there.

This repository is the reference implementation, the PayeeBench benchmark,
the mechanized models and the experiment harness described in the research
blueprint (v2 core, 3 October 2026). `python -m experiments.run_all`
regenerates every table and figure from fixed seeds; `results/REPORT.md` is
the generated report.

## Layout

| Blueprint component | Code |
|---|---|
| meridian-core: edges (Def. 1, typed per F2), scope lattice (Def. 2), typed issuance policy (Def. 3), PAV (Alg. 1), route grammar, committed routes and terminal continuity (F3), breach certificates (Thm 2), directory with scope-filtered reachability (Lemma 1), split verification (F5), decision log, VC 2.0 / SD-JWT encodings | `meridian/core/` |
| meridian-issuers: domain verifier (DNS-01 style), vLEI QVI, platform, PSP, payfac, acquirer, bank (VoP), escrow | `meridian/issuers/` |
| meridian-log: RFC 6962 Merkle log, signed tree heads, split views, brand monitors, objections, gossip, Alg. 3 acceptance with probation | `meridian/log/` |
| meridian-cba: UTS #39 skeletons, logo perceptual hash, sentence embeddings, noisy-OR confusability, margin rule (Alg. 2) | `meridian/cba/` |
| meridian-rws: rail profiles, window theorem (F4, Thm 3), scheduler (Alg. 4), closed-loop receipts (V3); ISO 8583, SEPA Instant + VoP sandbox, Stripe test mode adapters | `meridian/rws/` |
| meridian-zk: Poseidon Merkle-membership circuit (circom, Groth16), BBS edge credentials (IETF draft), k-anonymous and two-server PIR lookups (Alg. 5) | `zk/`, `meridian/zk/` |
| Protocol extensions: AP2 v0.2 mandates, ACP checkout + delegated payment, x402 (EIP-3009 on a local ledger, escrow), MPP-style challenge | `meridian/protocols/` |
| PayeeBench: ecosystem generator (S1-S13), attacks A1-A12 (+A13), premise-violation partition, baselines B1-B7, M1-M3, deterministic judges | `payeebench/` |
| Formal models: Tamarin (T1, T2, T4, T10, T11, P10, P18) and ProVerif (private lookup) | `formal/` |
| Experiments E1-E10, F3/T4/F5 checks, ablations, statistics, figures, report | `experiments/` |
| Pre-registration of H1-H5 (locked before E2-E6) | `preregistration/` |

## Running

Requirements: Python 3.12, Node 22, Tamarin 1.12 (with Maude), ProVerif 2.05.

```bash
make setup          # venv + pinned Python deps + npm deps
make zk             # compile the circuit and the Groth16 test setup (~3 min)
make test           # unit and property tests
make quick          # smoke run of everything
make reproduce      # full run -> results/REPORT.md, results/MANIFEST.sha256.json
```

Or with Docker (linux/amd64):

```bash
docker compose run --rm meridian           # full run, results written to ./results
docker compose run --rm meridian-offline   # everything except the passive web measurement (E10)
docker compose run --rm tests
```

Every run writes raw per-run CSV and JSON under `results/raw`, tables under
`results/tables` (Markdown and CSV), figures under `results/figures`, and a
SHA-256 manifest with the environment and git commit. E2, E5 and E6 refuse to
run if `preregistration/hypotheses.yaml` no longer matches
`preregistration/LOCK`.

## Live backends (optional)

The default run is fully offline except E10. These environment variables
switch individual parts to live services; the report records which backend
each number came from.

| Variable | Effect |
|---|---|
| `STRIPE_SECRET_KEY=sk_test_...` | E6 measures authorization and void latency on Stripe test mode (manual capture); a live key is refused |
| `MERIDIAN_AGENT_MODEL` plus the provider's API key | E9 hosted-model agents (scripted worst-case agents are always run) |

Not yet wired to live infrastructure: x402 on a public testnet (the local
ledger verifies real EIP-3009 signatures), issuer authorization records from
a real issuer (ISO 8583 fields are simulated), and real VoP endpoints.

## Scope and limitations

* PayeeBench attack outcomes are exact counts over constructed cases; they
  test the verifiers as specified, not deployed systems.
* Rail timing (windows, observer and void latencies) comes from
  `config/rails.yaml`; these are modelling assumptions, swept in E6.
* The SNARK proves membership and scope containment of an admitted route
  summary; signatures on the underlying edges are checked by the log at
  admission, so V4 soundness rests on admission (T5).
* The MPP header format is provisional until pinned to the upstream spec.
* E10 is passive: DNS, one TLS handshake and one homepage request per site,
  and GLEIF API lookups; LEI matches are name-based.
* The Groth16 setup uses fixed test entropy and must not protect real payments.

Upstream versions used are pinned in `data/upstream/PINS.txt`.
