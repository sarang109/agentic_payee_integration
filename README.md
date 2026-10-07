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

The repository backs two papers and an optional third. Each paper cites its
own archived release (version DOI on Zenodo), so its tables can be
regenerated exactly as reported. `v0.9.0` is a pre-submission snapshot, not
the release a paper cites. See `docs/RELEASING.md` for the release procedure.

Headline experiments per paper (the table after this one lists everything each
paper draws on):

| Paper | Experiments |
|---|---|
| Paper 1: Verifiable Discharge (IEEE TDSC) | E2, E3, E4/E4b/E4c, E5, E10/E10b, E12 (author-written, not independent; `e12/ERRATA.md`), the Tamarin models in `formal/`, T4 mutation tests, Stripe Connect X2/X3 |
| Paper 2: After Authorization (ACM TOPS, else IEEE TIFS) | E6, E9, E11, and the A11-A13 rows of E2/E3 |

| | Paper 1: Verifiable Discharge (IEEE TDSC) | Paper 2: After Authorization (ACM TOPS, else IEEE TIFS) | Paper 3 (optional): Private Payee Checks |
|---|---|---|---|
| Release | v1.x | v2.x | v3.x |
| Hypotheses | H1, H2 | H3, H4 (SNARK variant), H5, and H6 (pre-registered in `preregistration/hypotheses_v2.yaml`) | H4 privacy part |
| Theory | Hierarchy G0-G4 and Theorem 1, typed edges and Theorem 2, committed routes (F3), Proposition 4 (F5), Lemma 1 | Theorem 3 window condition (F4), T7, T8; Theorem 4 funded routes (F6) only if E11 passes | T9 |
| Supplement | `docs/supplement/proofs.md` Sections 1-6, `prior_art.md`, `baselines.md` | `docs/supplement/proofs.md` Sections 7-8 (and Theorem 4), `prior_art.md` | circuit details |
| Experiments | E1, E2/E3 (with the AIP-Bench external scenarios), E4/E4b/E4c (with the string-weak stress set), E5, E8, E10/E10b; F3 toy check, T4 mutations, F5 split; ablations 1-4 and 6 (4 is E5, 6 is E1); Stripe Connect X2/X3 (`stripe_connect`); E12 author-written attack set (not independent; see `e12/ERRATA.md`) | E6 (with timing sources), E9 (hosted-model agents, allowlist gate, synthetic benign tasks); E11 (funded routes, configuration M5 = M3 + F6); x402 on Base Sepolia; F4 toy; per-rail comparison (H5, RQ5 Pareto, BNPL supplement); ablation 5 (E6); Stripe test-mode void latency | E7 (V4 SNARK and BBS variants) |
| Formal models | `formal/tamarin/` (meridian_v1, meridian_g2, checkout_ext) | rail timing lemmas | `formal/proverif/` (private_lookup) |
| Code | `meridian/core`, `meridian/issuers`, `meridian/log`, `meridian/cba`, `meridian/protocols`, `payeebench/` | `meridian/rws`, `meridian/core/exposure.py`, `experiments/e11_exposure.py` | `meridian/zk`, `zk/` |

`make reproduce` runs every experiment. The v1 pre-registration
(`preregistration/hypotheses.yaml`, lock in `preregistration/LOCK`) is
unchanged between releases; the v2 file (`preregistration/hypotheses_v2.yaml`,
lock in `preregistration/LOCK_V2`) is added for H6 and records the SHA-256 of
the v1 file.

E10 queries live DNS, TLS and GLEIF and will not reproduce on a later run:
the archived results carry the measurement date. Kaggle and phishing data are
git-ignored and not archived. The Groth16 setup uses fixed
test entropy and must not protect real payments.

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
| `MERIDIAN_AGENT_MODEL` (e.g. `gpt-4o-mini-2024-07-18`) plus `OPENAI_API_KEY` | E9 hosted-model agents in the AgentDojo banking suite (scripted worst-case agents always run). The archived run in `results/raw/e9_hosted_runs.csv` is reused unless `MERIDIAN_E9_RERUN=1`; a full run makes about 5,900 model calls (about 6.5 M input tokens). Only outcomes, token counts and timings are stored, never transcripts. |
| `MERIDIAN_X402_KEY_FILE` (path to a Base Sepolia test key holding test USDC) | x402 `exact` payments through the public facilitator on Base Sepolia, a tampered-recipient and a mismatched-recipient case; transaction hashes are archived. Reused unless `MERIDIAN_X402_RERUN=1`. |

No cloud-provider credentials are needed. When no Stripe key is set, E6
replays the archived Stripe test-mode void-latency measurement and says so.
Not wired to live infrastructure: the escrow contract (local ledger only),
issuer authorization records from a real issuer (ISO 8583 fields are
simulated), and real VoP endpoints.

## Datasets

| Dataset | Used by | How it is obtained |
|---|---|---|
| Tranco list 56WKN (top 20,000) | E4, E4b | checked in as `data/tranco/tranco_56WKN_top20k.csv` |
| UCI PhiUSIIL Phishing URL Dataset (CC BY 4.0) | E4b | downloaded on first run and verified by SHA-256 |
| Kaggle: Adversarial Homograph Detection (alishan07, CC BY-SA 4.0), Malicious URLs (sid321axn, CC0), Phishing Site URLs (taruntiwarihp), PhishTank 2026 (quangnguynv, Apache-2.0) | E4c | downloaded with the Kaggle CLI when a token is configured (`~/.kaggle/access_token` or `KAGGLE_API_TOKEN`); SHA-256 recorded in `results/tables/e4c_files.md` |
| Unicode `confusables.txt` 18.0.0 | CBA | checked in |
| AgentDojo banking suite v1 | E9 | `agentdojo==0.1.35` |
| GLEIF LEI records, DNS, TLS certificates, storefront homepages | E10, E10b | queried live (passive), cached under `results/cache/`; extracted features are archived in `results/raw/e10*.csv` |
| Tranco list 56WKN (full top 1M, `data/tranco/top-1m.csv.zip`, not committed) | E10b | downloaded from tranco-list.eu (list 56WKN); the first 20,000 rows equal the committed extract |
| AIP-Bench scenarios (Louck, arXiv 2607.21824; CC BY 4.0) | E2 external scenarios | scenario descriptions summarised in `payeebench/cases.py` (`AIP_SCENARIOS`), not redistributed |

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
* E10b samples storefronts from the Tranco list with a marker-based
  classifier; storefronts rendered entirely in JavaScript are missed.
* The hosted-model E9 runs depend on the provider's model at the time of the
  run; the archived run records the model ID and date.

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
