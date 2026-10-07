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

## Papers and releases

The repository backs two papers. Each paper cites its own archived release
(version DOI on Zenodo), so its tables can be regenerated exactly as
reported. See `docs/RELEASING.md` for the release procedure.

| | Paper 1: Verifiable Discharge (authority-to-receive verification) | Paper 2: Closing the Loop (window-safe settlement checks and private payee proofs) |
|---|---|---|
| Release | v1.x | v2.x |
| Hypotheses | H1, H2 | H3, H4, H5 |
| Theory | Hierarchy G0-G4 and Theorem 1, typed edges and Theorem 2, committed routes (F3), Proposition 4 (F5), Lemma 1 | Theorem 3 window condition (F4), T7, T8, T9 |
| Experiments | E1, E2/E3, E4/E4b/E4c, E5, E8, E10; F3 toy check, T4 mutations, F5 split; ablations 1-3 and the E4 CBA ablation; Stripe Connect X2/X3 (`stripe_connect`) | E6, E7, E9; F4 toy; per-rail comparison (H5); Stripe test-mode void latency |
| Formal models | `formal/tamarin/` (meridian_v1, meridian_g2, checkout_ext) | `formal/proverif/` (private_lookup) |
| Code | `meridian/core`, `meridian/issuers`, `meridian/log`, `meridian/cba`, `meridian/protocols`, `payeebench/` | `meridian/rws`, `meridian/zk`, `zk/` |

`make reproduce` runs both sets; the pre-registration (`preregistration/`)
covers all five hypotheses and is unchanged between releases.

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

The default run is offline except E10 (passive web measurement) and the
first E4b run (downloads the dataset). These environment variables switch
parts to live services; the report records which backend each number came
from. Keys are read from the environment only and are never written to
`results/`.

| Variable | Effect |
|---|---|
| `STRIPE_SECRET_KEY=sk_test_...` | E6 measures authorization and void latency on Stripe test mode (30 manual-capture PaymentIntents, each cancelled); the rail simulations then use the measured latency. A live-mode key is refused. |
| same key, with Connect enabled on the test account (and the platform's loss responsibilities acknowledged) | `stripe` step creates Accounts v2 recipient accounts and reproduces X2 (separate charges and transfers to the wrong connected account, transfer reversed) and X3 (payout bank account changed) on Stripe Connect test mode. Enable Connect in the Dashboard (test mode, Connect > Get started). |
| `MERIDIAN_AGENT_MODEL` plus the provider's API key | E9 hosted-model agents (scripted worst-case agents always run) |

No cloud-provider credentials are needed. Not yet wired to live
infrastructure: x402 on a public testnet (the local ledger verifies real
EIP-3009 signatures), issuer authorization records from a real issuer (ISO
8583 fields are simulated), and real VoP endpoints.

## Datasets

| Dataset | Used by | How it is obtained |
|---|---|---|
| Tranco list 56WKN (top 20,000) | E4, E4b | checked in as `data/tranco/tranco_56WKN_top20k.csv` |
| UCI PhiUSIIL Phishing URL Dataset (CC BY 4.0) | E4b | downloaded on first run and verified by SHA-256 |
| Kaggle: Adversarial Homograph Detection (alishan07, CC BY-SA 4.0), Malicious URLs (sid321axn, CC0), Phishing Site URLs (taruntiwarihp), PhishTank 2026 (quangnguynv, Apache-2.0) | E4c | downloaded with the Kaggle CLI when a token is configured (`~/.kaggle/access_token` or `KAGGLE_API_TOKEN`); SHA-256 recorded in `results/tables/e4c_files.md` |
| Unicode `confusables.txt` 18.0.0 | CBA | checked in |
| AgentDojo banking suite v1 | E9 | `agentdojo==0.1.35` |
| GLEIF LEI records, DNS, TLS certificates, storefront homepages | E10 | queried live (passive), cached under `results/cache/` |

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

Upstream protocol versions used are pinned in `data/upstream/PINS.txt`.

## Reproducibility notes

* E10 queries live DNS, TLS and GLEIF. A rerun gives different numbers; the
  archived results under `results/` record the collection date.
* Stripe results come from test mode only; no live money is moved.
* Kaggle and UCI datasets are downloaded at run time and are not
  redistributed; their SHA-256 hashes are recorded in the report.

## License and citation

Code is released under the Apache License 2.0 (`LICENSE`). Bundled
third-party data (Unicode `confusables.txt`, the Tranco list extract) keeps
its own terms; see `NOTICE`. To cite, use the version DOI of the release you
used; `CITATION.cff` has the metadata.
