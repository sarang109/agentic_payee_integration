# Releasing an archived artifact

Zenodo archives every *published* GitHub release of this repository (not
bare tags, not drafts). An archived version and its DOI are permanent: a
mistake is fixed by a new version, never by editing or moving a tag. Never
move a tag after submission.

## Release map

| | Snapshot | Paper 1 (IEEE TDSC) | Paper 2 (ACM TOPS, else IEEE TIFS) | Paper 3 (optional) |
|---|---|---|---|---|
| Tag | `v0.9.0` | `v1.0.0` | `v2.0.0` | `v3.0.0` |
| Release title | MERIDIAN pre-submission snapshot | MERIDIAN artifact for Paper 1: Authority to Receive (v1.0.0 and v1.0.1 used the working title "Verifiable Discharge") | MERIDIAN artifact for Paper 2: After Authorization | settled with the scoped claim and venue |
| Cut when | now; it is not the release a paper cites | Gate A passed and Paper 1 results frozen, before the preprint | Gate B passed and Paper 2 results frozen | scoped claim and venue settled |
| Hypotheses in the release | `hypotheses.yaml` H1-H5 and its lock, unchanged | same file; H1 and H2 verdicts | same file for H3-H5, plus `hypotheses_v2.yaml` and its lock for H6 | H4 privacy part |
| After reviews | none | `v1.1.0`, `v1.2.0` | `v2.1.0`, `v2.2.0` | |
| Paper cites | nothing | version DOI of the release reviewed | version DOI of its release; Paper 2's record links Paper 1's DOI | |

Paper 1 is the foundation and the attacks it stops; Paper 2 is everything
that happens after authorization (window condition, scheduler, receipts,
and funded routes only if E11 validates them); Paper 3 is the V4 privacy
work. The README "Papers and releases" section carries the same map with
experiments, directories and formal models per paper.

## What each release contains

A release is the whole repository at the tagged commit. What differs is which
experiments, hypotheses and proofs the paper relies on.

| | v0.9.0 snapshot | v1.0.0 (Paper 1) | v2.0.0 (Paper 2) |
|---|---|---|---|
| Experiments reported | all current: E1-E10b, ablations 1-6, F3 toy check, T4 mutations, F5, Stripe X2/X3, x402 on Base Sepolia, hosted-model E9 | E1-E5, E8, E10, E10b, ablations 1-4 and 6, X2/X3, toy check, T4, F5, E12 | E6, E9, E11, x402, F4 toy, per-rail comparison, ablation 5, Stripe void latency (E7 only if V4 stays) |
| Formal models | all Tamarin and ProVerif models | Tamarin models and the lemma table, including the variants expected to fail | rail timing lemmas (ProVerif only if V4 stays) |
| Code added | none | E12 harness and the frozen attack file with its hash | `meridian/core/exposure.py`, `tests/test_exposure.py`, `experiments/e11_exposure.py` |
| Supplement | `docs/supplement/*` as it stands | proofs of Theorems 1 and 2, Proposition 4 and Lemma 1 after reviewer comments; `baselines.md`; `prior_art.md` with no abstract-only citations | proofs of Theorems 3 and 4, T7, T8; E11 sensitivity tables |
| Must not be missing | notes on the shared generator and re-specified baselines | reviewer comments on the proofs addressed | the kill-rule outcome for F6 recorded |

Every release also needs `results/` regenerated at the commit being tagged,
manifest hashes compared in a clean Docker run, a clean secrets search, and
the Groth16 test-entropy warning in the notes.

## One-time setup

- [ ] Zenodo GitHub switch is on for `sarang109/agentic_payee_integration`
      (Zenodo only archives releases made after it is switched on).
- [ ] `LICENSE`, `NOTICE`, `CITATION.cff` and `.zenodo.json` exist. Check
      which of `.zenodo.json` and `CITATION.cff` Zenodo uses when they
      disagree on the record, and keep the two consistent.
- [ ] `gh auth login` (only needed to publish the release from the command line).

## Before each release

- [ ] Every experiment the paper reports exists in the code (ablations 1-3
      are in `experiments/ablations.py`; ablation 4 is E5, 5 is E6, 6 is E1).
- [ ] The gate the release depends on has passed (see the publication plan):
      Gate A for v1.0.0, Gate B for v2.0.0. The snapshot sits outside the gates.
- [ ] `.zenodo.json`: if the paper is on arXiv, add
      ```json
      "related_identifiers": [
        {"identifier": "arXiv:XXXX.XXXXX", "relation": "isSupplementTo", "scheme": "arxiv"}
      ]
      ```
      For v2.x, also add Paper 1's version DOI with relation `isSupplementTo`
      or `references`.
- [ ] Search the tree for keys and transcripts:
      `git grep -nIE 'sk_(test|live)_|rk_(test|live)_|BEGIN .*PRIVATE KEY'`.
      `results/raw` for v2.x holds hosted-model E9 runs: check them too.
- [ ] Regenerate results at the commit that will be tagged:
      ```bash
      make test
      make reproduce          # or: docker compose run --rm meridian
      ```
      The report and manifest record the commit they were generated from.
      Commit `results/` on its own, so the tagged commit differs from that
      commit only in `results/`; regenerate if any code changes after this.
- [ ] Repeat the run in a clean Docker container and compare manifest hashes
      (E10 and live-backend numbers are expected to differ). For v1.0.0 this
      means two clean reproduce runs with matching hashes.
- [ ] E10 queries live DNS, TLS and GLEIF and does not reproduce on a later
      run: the cached results and the measurement date are archived and the
      README says so.
- [ ] Kaggle files stay out of the repository (check each licence); archive
      extracted features and hashes instead of third-party page content.

## Publishing

```bash
git tag -a v0.9.0 -m "MERIDIAN pre-submission snapshot"
git push origin v0.9.0
gh release create v0.9.0 --verify-tag \
  --title "MERIDIAN pre-submission snapshot" \
  --notes-file release-notes-v0.9.0.md
```

Replace the tag, title and notes file for v1.0.0 and v2.0.0. Release notes
say which experiments and hypotheses are in scope, what does not reproduce
exactly (E10, live Stripe timings), the known limits, and the Groth16
test-entropy warning. Repeat that warning in every release: the Groth16
setup uses fixed test entropy and must not protect real payments.

## After publishing

1. Open the new record on Zenodo; check the title, license, creators and file list.
2. Record the **version** DOI. Cite the version DOI in each paper's artifact
   statement; use the **concept** DOI for the README badge (first release only).
3. Do not cite the v0.9.0 snapshot in a submitted paper as the reviewed release.
4. For a paper release, only then post the preprint and submit.
