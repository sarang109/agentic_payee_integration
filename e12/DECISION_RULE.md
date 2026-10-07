# E12 decision rule

Written before any E12 run and locked with the attack file (`e12/LOCK`). It
is not edited after the freeze. If the rule turns out to be wrong, that is
reported next to the result, not fixed in place.

## Purpose

E12 answers the circular-evaluation objection: the attacks, the legitimate
structures and the strongest baseline B7 in the main benchmark share one
generator and grammar. E12 uses attacks written by authors who have not seen
that generator, against the same configurations, and reports the result
whatever it shows. It is Gate A of the publication plan.

## Procedure

1. Authors write attacks from `docs/e12/AUTHORING.md` only (the threat model
   and the schema). They do not read `payeebench/`, `results/`, `docs/` other
   than that file, or the experiment code.
2. The attack file `e12/attacks.json` is validated (`python -m
   experiments.e12_independent validate`). Validation compiles every attack on
   a fresh world and uses ground truth only: an attack must divert the money to
   an illegitimate terminal if every check allows it. Validation never
   evaluates a configuration, so no attack can be tuned against a result.
3. At least 30 attacks by at least two distinct authors. The file is frozen
   (`freeze`): its SHA-256 and this file's SHA-256 go into `e12/LOCK`. After
   the freeze no attack is added, edited or removed.
4. `run` evaluates B1-B7, M1-G1, M1, M2 and M3 once on the frozen set with the
   world seed 12012 and the anchoring calibration from E4 (`cba_calibration`).
   Every run is appended to `e12/RUN_LOG.jsonl`; a later run must reproduce
   the first, and the log records whether it does. Any code change after the
   first run is disclosed next to the result.

## Quantities

* An attack is *in-model* unless its author set `premise_violation`; the
  premise-violation attacks are reported separately and are not part of the
  decision.
* *Loss* for a configuration and an attack: the payment is executed (ALLOW, or
  STEP-UP the user confirms) to a terminal that is not legitimate for the
  intended brand, and it is not undone. This is the judge used in E2.
  STEP-UP without user confirmation is not a loss.
* The configurations declared for the decision are B7 (strongest baseline) and
  M2 (M1 plus V2: anchoring and the transparency log with probation). M1 is
  reported for the paired comparison with B7.

## Confirmatory test (one)

M2 against B7 on the in-model attacks: a paired exact McNemar test (two-sided
binomial on the discordant attacks), alpha = 0.05.

* `advantage-holds`: M2 has more attacks stopped than B7 (fewer losses) and
  p < 0.05.
* `advantage-not-significant`: M2 has fewer or equal losses but p >= 0.05.
* `advantage-reversed`: B7 has fewer losses than M2 (any p).

Wording consequences, applied in the paper:

* `advantage-holds`: "outperforms" may be used for M2 against B7 on the
  independent set, with the counts and p.
* `advantage-not-significant`: the shrunken result is reported as it is; no
  "outperforms" language anywhere in the paper.
* `advantage-reversed`: the reversal is reported; no "outperforms" language;
  Paper 1 is reframed around the framework (hierarchy, typed edges,
  attributability) and the X2/X3 findings.

## Reported regardless

The full attack matrix with exact counts per configuration, the paired tests
for M1 against B7, M2 against M1, M3 against M2, M1 against M1-G1 and M3
against B7 (exploratory, not corrected for multiple comparisons), the losses
by scenario kind, and the M2 against B7 comparison by author. The counts of
attacks per author and per scenario kind. The compiled attacks that were
removed before the freeze because they did not divert, and why.

## Limits to state in the paper

* The attacks are compiled onto the same world builder as the main benchmark.
  Independence is in the choice of scenario, victim and parameters, not in the
  infrastructure or the legitimate structures. False blocks and step-up on
  legitimate payments are not re-measured here (E3 reports them).
* The scenario kinds in the schema bound what an author can express; kinds
  added before the freeze are listed in the schema changelog.
* The set is small; the confidence interval on a difference of this size is
  wide. The McNemar test conditions on the discordant attacks.
