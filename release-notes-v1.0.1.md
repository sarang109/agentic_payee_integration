# MERIDIAN artifact for Paper 1: Verifiable Discharge (v1.0.1)

A correction release for `v1.0.0`. `v1.0.0` stays archived and unchanged; this
version replaces it as the release to cite. It is the whole repository at the
tagged commit, has not been through peer review, and Paper 1's scope is as
described in the `v1.0.0` notes.

## What changed since v1.0.0

- The E12 runner is renamed from `experiments/e12_independent.py` to
  `experiments/e12_author_written.py`, and the `make e12` target and its
  callers (`experiments/run_all.py`, `tests/test_e12.py`) follow. The attacks
  were written by the project author after the generator, with the generator
  in view, so the old name overstated what E12 is. `e12/ERRATA.md` records the
  rename.
- `e12/DECISION_RULE.md` and `e12/attacks.json` are hash-locked and not
  edited. The decision rule still names the old module in its validation
  command; read that as the new module name.
- No attack, configuration, seed, decision logic or experiment code changed.
  Nothing in `results/` was regenerated, and none of its numbers move.
- `CITATION.cff` is updated to this version.

## Everything else

The scope, verdicts, known limits and reproducibility notes in
`release-notes-v1.0.0.md` apply unchanged, including the E12 limits (author-
written, 50 in-model attacks, p just under 0.05 on 17 discordant attacks).

- **Groth16 warning:** the setup in `zk/` uses fixed test entropy and must not
  protect real payments.
