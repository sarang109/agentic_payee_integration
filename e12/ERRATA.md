# E12 errata: who wrote the attacks

Added after the freeze and after the first run. `attacks.json` and
`DECISION_RULE.md` are hash-locked (`e12/LOCK`) and are not edited, so the
correction is recorded here and in the text around the results.

## Correction

`DECISION_RULE.md` (Purpose and Procedure) and earlier text in the README, the
report and the code docstrings describe the E12 attacks as written by
independent authors who had not seen the PayeeBench generator and who worked
from `docs/e12/AUTHORING.md` alone. That was not the case.

* The attacks were written inside the project, by the same side that built
  the generator, with the repository, the generator, the baselines and the
  MERIDIAN code in view. The authoring protocol in `docs/e12/AUTHORING.md`
  (read only that file, read no code) was not followed.
* `author-1` and `author-2` are two labels used to split the file into two
  batches. They are not two independent people and the by-author table is not
  evidence of independence between authors.
* E12 is therefore an author-written, author-dependent attack set. It does not
  answer the circular-evaluation objection that `DECISION_RULE.md` says it
  answers. It still tests something: the attacks were chosen from the schema
  in `AUTHORING.md`, compiled onto the world builder, validated against ground
  truth only, and frozen before any configuration was evaluated, so they were
  not tuned against a result. What it cannot show is that the attacks are
  free of the generator's assumptions.

## Commit messages and other early text

The messages of commits `c64f04d` and `2ccfda6` call the attack set
"independent", and the same word appears in `DECISION_RULE.md` and in the
history of the files this commit corrected. History is not rewritten, so this
file is the correction for all of them: wherever the repository's history says
the E12 attacks were independent, read it as author-written.

## Consequence for the decision rule

The rule's wording consequences ("outperforms" may be used on the
independent set) were written for an independent set. The label recorded in
`results/raw/e12_summary.json` (`advantage-holds`, 50 in-model attacks, M2 14
losses, B7 23, p = 0.049) is unchanged, but the "outperforms" wording that
accompanies it is not licensed: the result is evidence on an author-written
set and is to be reported as such, alongside the main-benchmark results, not
as an independent confirmation. The p-value is just under 0.05 on 17
discordant attacks, so it should not carry more weight than that.

## Attacks removed before the freeze

The decision rule requires reporting compiled attacks that were removed
before the freeze because they did not divert. The repository records none:

* `attacks.json` was committed once (`c64f04d`), in its final form, 52
  attacks with contiguous ids (`A1-01`..`A1-27`, `A2-01`..`A2-25`).
* `freeze` validated every attack against ground truth at the time of the
  freeze and refuses to freeze if any attack does not divert; it froze.
* Drafts written before that commit were not archived, so the repository
  cannot show whether any draft attack was dropped earlier. Nothing in it
  indicates one was.

Three attacks the schema could not express are listed under `unexpressible`
in `attacks.json`; they were not run and were not part of the decision.

## Changes after the first run

After the first run, wording only changed (this file, the report text, table
titles and captions, docstrings, the README, the v0.9.0 release notes). No
attack, configuration, seed or decision logic changed. The E12 tables were
regenerated for the new titles, and `RUN_LOG.jsonl` records that the rerun
reproduced the first result.
