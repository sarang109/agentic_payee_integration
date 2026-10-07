# MERIDIAN pre-submission snapshot (v0.9.0)

A dated, citable record of the repository before either paper is submitted.
**It is not the release a paper cites and it is not peer reviewed.** The
reviewed releases are v1.0.0 (Paper 1) and v2.0.0 (Paper 2).

## What is in it

The whole repository at the tagged commit:

- reference implementation (`meridian/`), PayeeBench generator and judges (`payeebench/`)
- experiments E1-E10b, ablations 1-6, the F3 toy check, T4 mutation tests, F5 split check
- Stripe Connect test-mode reproduction of X2 and X3, Stripe test-mode void latency
- x402 on Base Sepolia (public testnet), hosted-model E9 (one model, 1,516 runs)
- Tamarin and ProVerif models (`formal/`)
- pre-registration of hypotheses H1-H5 (`preregistration/hypotheses.yaml`, lock in `preregistration/LOCK`), unchanged
- supplement notes (`docs/supplement/`), regenerated results (`results/`) with a SHA-256 manifest

`make test` and `make reproduce` regenerate the tables and figures from fixed seeds.

## Verdicts recorded in `results/REPORT.md`

H1 supported; H2 partly supported (security part yes, the 5% benign step-up
target not met); H3 supported; H4 supported for the SNARK variant only; H5
not supported. Failed targets are reported as failed.

## Known limits (read before using any number)

- PayeeBench attacks, legitimate structures and the strongest baseline B7 are
  built from one generator and grammar, so a 0% false-block rate on those
  structures is partly by construction. Baselines B1-B7 are re-specified from
  their public descriptions, not independent reimplementations. The
  independently authored attack set (E12) is not in this snapshot.
- The proofs of Theorems 1 and 2 and Proposition 4 have not been reviewed by
  anyone outside the project; treat them as proof sketches.
- ISO 8583 authorization data is simulated; no real issuer data was available.
- Rail windows, observer latencies and every void or recall latency except the
  Stripe card void and the x402 testnet measurements are modelled
  (`config/rails.yaml`). Simulated rails and constructed cases are not
  evidence about deployed systems.
- Hosted-model E9 covers a single model (gpt-4o-mini-2024-07-18).
- E10 and E10b query live DNS, TLS and GLEIF and do not reproduce on a later
  run; the archived results carry the measurement date. The US storefront
  sample in E10b has 58 sites.
- Custodian deviation on the card rail is undone by no mode (attributable, not
  prevented); the BBS variant of V4 misses the 150 ms payer-side target.
- The agency-law premise behind verifiable discharge has not been reviewed
  by counsel and is stated as an assumption; this is not legal advice.
- Some `docs/supplement/prior_art.md` entries are marked abstract-only.

## Reproducibility

- Test keys only, no live money; Stripe in test mode only.
- Third-party datasets (Kaggle, phishing feeds) are not archived.
- **Groth16 warning:** the setup in `zk/` uses fixed test entropy and must not
  protect real payments.
