# MERIDIAN artifact for Paper 1: Authority to Receive (v1.0.2)

A metadata correction release for `v1.0.0` and `v1.0.1`. Paper 1 is titled
*Authority to Receive: Verifiable Payee Chains for Agentic Payments* (IEEE
TDSC). The earlier releases, their notes (`release-notes-v1.0.0.md`,
`release-notes-v1.0.1.md`), some code comments and the results used the
working title *Verifiable Discharge*. It is the same paper. Archived notes and
tags are not edited, so this release carries the correction.

## What changed since v1.0.1

- `.zenodo.json`, the README paper map and `docs/RELEASING.md` give the paper's
  title and say that the working title appears elsewhere in the archive.
- `CITATION.cff` is updated to this version.
- No code, attack, configuration, seed, result or number changed. The scope,
  verdicts and known limits in `release-notes-v1.0.0.md` and the E12 rename in
  `release-notes-v1.0.1.md` apply unchanged. E12 remains an author-written
  attack set.

## Reproducibility

- **Groth16 warning:** the setup in `zk/` uses fixed test entropy and must not
  protect real payments.
