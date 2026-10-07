# Releasing an archived artifact

Zenodo archives every *published* GitHub release of this repository (not
bare tags, not drafts). An archived version and its DOI are permanent: a
mistake is fixed by a new version, never by editing or moving a tag.

| | Paper 1 (IEEE TDSC) | Paper 2 (ACM TOPS) |
|---|---|---|
| Tag | `v1.0.0` | `v2.0.0` |
| Release title | MERIDIAN artifact for Paper 1: Verifiable Discharge | MERIDIAN artifact for Paper 2: Closing the Loop |
| When | Paper 1 results frozen, before the arXiv post and submission | Paper 2 results frozen, before submission |
| Revisions | `v1.1.0`, `v1.2.0` | `v2.1.0`, `v2.2.0` |

## One-time setup

- [ ] Zenodo GitHub switch is on for `sarang109/agentic_payee_integration`
      (Zenodo only archives releases made after it is switched on).
- [ ] Add your ORCID to `.zenodo.json` (`"orcid": "0000-0000-0000-0000"`
      under the creator) and to `CITATION.cff` (`orcid: "https://orcid.org/..."`).
      Add `"affiliation"` too if you want it on the record.
- [ ] `gh auth login` (only needed to publish the release from the command line).

## Before each release

- [ ] Section 7 fixes of the publication plan that belong to this paper are
      closed or written up as limitations.
- [ ] Every experiment the paper reports exists in the code. As of
      2026-10-06, ablations 4, 5 and 6 from the plan are not implemented
      (`experiments/ablations.py` has 1-3).
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
      `results/raw` for v2.x will hold hosted-model E9 runs: check them too.
- [ ] Regenerate results at the commit that will be tagged:
      ```bash
      make test
      make reproduce          # or: docker compose run --rm meridian
      ```
      The report and manifest record the commit they were generated from.
      Commit `results/` on its own, so the tagged commit differs from that
      commit only in `results/`; regenerate if any code changes after this.
- [ ] Repeat the run in a clean Docker container and compare manifest hashes
      (E10 and live-backend numbers are expected to differ).

## Publishing

```bash
git tag -a v1.0.0 -m "MERIDIAN artifact for Paper 1: Verifiable Discharge"
git push origin v1.0.0
gh release create v1.0.0 --verify-tag \
  --title "MERIDIAN artifact for Paper 1: Verifiable Discharge" \
  --notes-file release-notes.md
```

Release notes: scope (which experiments and hypotheses), what does not
reproduce exactly (E10, live Stripe timings), known limits, and the Groth16
test-entropy warning.

## After publishing

1. Open the new record on Zenodo; check the title, license, creators and file list.
2. Copy the **version** DOI (not the concept DOI) into the paper's artifact
   statement.
3. Add the **concept** DOI badge to `README.md` (first release only).
4. Only then post the arXiv preprint and submit.
