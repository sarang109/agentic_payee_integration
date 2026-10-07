# MERIDIAN artifact for Paper 1: Verifiable Discharge (v1.0.0)

The release that Paper 1 (IEEE TDSC, *Verifiable Discharge*) cites. It is the
whole repository at the tagged commit; Paper 1 relies on the parts listed
below. It has not been through peer review. The earlier `v0.9.0` release is a
pre-submission snapshot and is not the release a paper cites.

## What Paper 1 relies on

- Reference implementation (`meridian/core`, `meridian/issuers`, `meridian/log`,
  `meridian/cba`, `meridian/protocols`) and the PayeeBench generator and judges
  (`payeebench/`)
- Experiments E1-E5, E8, E10, E10b, ablations 1-4 and 6, the F3 toy check, T4
  mutation tests, the F5 split check, Stripe Connect test-mode reproduction of
  X2 and X3
- E12, the frozen attack set with its decision rule, lock and run log
  (`e12/`). The attacks are author-written: the author wrote the generator
  first and the attacks afterwards, with the generator in view. E12 is
  therefore not independent of the generator and does not answer the
  circular-evaluation objection. See `e12/ERRATA.md`.
- Tamarin models (`formal/tamarin/`: `meridian_v1`, `meridian_g2`,
  `checkout_ext`)
- Pre-registration of hypotheses H1-H5 (`preregistration/hypotheses.yaml`, lock
  in `preregistration/LOCK`), unchanged since the lock
- Supplement notes (`docs/supplement/`) and results (`results/`) with a SHA-256
  manifest

The repository also contains code and results for Paper 2 (E6, E9, E11 and the
rail timing material). Paper 1 does not rely on them.

## Verdicts for Paper 1 (`results/REPORT.md`)

H1 supported. H2 partly supported: the security part holds, the 5% benign
step-up target is not met. Failed targets are reported as failed.

E12 (decision rule `e12/DECISION_RULE.md`, run once on the frozen set): M2
against B7 on 50 in-model attacks, M2 14 losses and B7 23, exact McNemar
p = 0.049 on 17 discordant attacks, label `advantage-holds`. The rule's
"outperforms" wording was written for an independent set and is not licensed
for this author-written one; the result is evidence on an author-written set.

## Changes since v0.9.0

- E12 added: harness, schema, frozen attack file (`e12/LOCK`), decision rule,
  run log, errata.
- `verify_route` now checks each custodian commitment's amount and currency
  against the payment (reasons `commitment-amount`, `commitment-currency`).
  Before, a commitment for a different amount or currency was accepted, and a
  smaller committed amount would let a custodian forward less without a breach.
- A spent-nonce store (`meridian/core/nonces.py`) lets a verifier refuse a
  binding token it has already allowed (`nonce-spent`). It is opt-in
  (`spent=` argument of `pav` and `verify_route`) and no benchmark
  configuration enables it.
- Upstream check of baseline B2 against the pinned AP2 SDK (`upstream_check`),
  which Paper 1 uses to ground its strongest re-specified baseline.
- Funded routes (F6), E11 and the hosted-model E9 runs are also in the tree but
  belong to Paper 2.

## Which results were regenerated

`results/` and the header of `results/REPORT.md` come from commit `95bca57`.
The commits after it change wording, the E12 errata, README and citation
metadata, and one code change: the commitment amount and currency check and the
opt-in nonce store above. Nothing in `results/` was rewritten for that code
change. To check that it moves no number, these steps were rerun at a later
commit in a copy of the repository and compared with the archived files:

- Rerun, identical apart from timing columns: toys (F3, T4 and the rest of
  that step), E1, E2/E3 with the AIP-Bench and BNPL supplements, E4, E5, E6,
  E8, E11, E12, ablations. The timing columns that differ are latencies and
  the time-limited F5 split search (nodes searched and seconds).
- Archived from the earlier run, not rerun: E4b and E4c (third-party data is
  not archived), E7, E9 (hosted API, one model), E10 and E10b (live network),
  x402 on Base Sepolia, Stripe Connect and Stripe void latency (test-mode
  keys), the upstream B2 check (network), and the formal models.

Neither new commitment reason nor `nonce-spent` occurs in any rerun table. The
results were not regenerated in a clean container, and two clean runs with
matching manifest hashes have not been made.

## Known limits (read before using any number)

- PayeeBench attacks, legitimate structures and the strongest baseline B7 are
  built from one generator and grammar, so a 0% false-block rate on those
  structures is partly by construction. E12 does not remove this: its attacks
  were written with the generator in view. Baselines B1-B7 are re-specified
  from their public descriptions, not independent reimplementations.
- The proofs of Theorems 1 and 2 and Proposition 4 have not been reviewed by
  anyone outside the project; treat them as proof sketches.
- ISO 8583 authorization data is simulated; no real issuer data was available.
- Rail windows, observer latencies and every void or recall latency except the
  Stripe card void and the x402 testnet measurements are modelled
  (`config/rails.yaml`). Simulated rails and constructed cases are not
  evidence about deployed systems.
- E10 and E10b query live DNS, TLS and GLEIF and do not reproduce on a later
  run; the archived results carry the measurement date. The US storefront
  sample in E10b has 58 sites.
- E12 is small (50 in-model attacks); its one confirmatory p-value is just
  under 0.05 and conditions on 17 discordant attacks.
- The agency-law premise behind verifiable discharge has not been reviewed
  by counsel and is stated as an assumption; this is not legal advice.
- Some `docs/supplement/prior_art.md` entries are marked abstract-only.

## Reproducibility

- Test keys only, no live money; Stripe in test mode only.
- Third-party datasets (Kaggle, phishing feeds) are not archived.
- `make test` and `make reproduce` regenerate the tables and figures from
  fixed seeds, except where noted above.
- **Groth16 warning:** the setup in `zk/` uses fixed test entropy and must not
  protect real payments.
