# MERIDIAN results

Generated 2026-10-06T17:31:42Z from commit `ba288649c4a38f32e646962396df2c0295fc32e0`, seed 7. Pre-registration SHA-256 `278ce8f17fe374e7ae7e424d83346b8ee559f779093b3c8f2ae740558d43cc99` (matches the lock).

## Run status

| step | status | seconds |
|---|---|---|
| ablations | ok | 1.4 |
| e1 | ok | 3.8 |
| e10 | ok | 116.8 |
| e2 | ok | 16.7 |
| e4 | ok | 77.8 |
| e5 | ok | 20.0 |
| e6 | ok | 4.3 |
| e7 | ok | 110.2 |
| e8 | ok | 28.8 |
| e9 | ok | 5.1 |
| formal | ok | 9.6 |
| toys | ok | 108.6 |

## Hypotheses (decision rules fixed in preregistration/hypotheses.yaml)

| hypothesis | verdict | evidence |
|---|---|---|
| H1 V1 admits no out-of-closure payee; baselines do; false blocks <= 1% | supported | M1 loss on A3/A4/A5/A7/A8: 0/300; baselines: {'B1': 281, 'B2': 273, 'B3': 300, 'B4': 290, 'B5': 300}; M1 false-block rate 0.000 [0.000, 0.004] |
| H2 V2 lowers lookalike success; benign step-up <= 5% (E4) | partly supported: security part yes, step-up target not met | A1-A2 loss M2 0/120 vs M1 120/120 (McNemar p = 1.5e-36); E4 held-out benign step-up 0.154 [0.129, 0.184] with 30% of brands impersonated; by impersonated share: 0.05 -> 0.023; 0.2 -> 0.097; 0.5 -> 0.218; 1 -> 0.438. Attack-dense bench (35% of brands impersonated, ~1.6 exact-name clones each): 0.178 [0.155, 0.203] |
| H3 card POST detection when POST-safe holds; instant rails need PRE or escrow | not supported | card: POST-safe probability 0.995, first-hop swaps voided before capture 395/400 = 0.9875, 95% CI [0.971, 0.995] against the 0.99 threshold; instant and stablecoin late evidence: POST undone 0/2400, ESCROW undone 2394/2400 (the instant-rail part holds; the card part misses the fixed threshold on the point estimate) |
| H4 V4 keeps decisions; payer p95 <= 150 ms | supported | agreement 1.000 [0.985, 1.000] on 250 cases; payer-side p95 12.7 ms; prover p95 632 ms |
| H5 no single version dominates every rail | supported | best MERIDIAN configuration per rail: {'a2a_instant': 'M3', 'bnpl': 'M1', 'card': 'M3', 'psp_token': 'M3', 'stablecoin': 'M3', 'wallet': 'M3'} |

Formal models: all results as expected (30 lemma results). F3 toy table: 13/14 rows match the blueprint. T4 mutation tests: 36/36 pass. E1 V1a/V1b agreement: 1.000 [0.995, 1.000] on allow vs block, 0.957 [0.941, 0.969] exact.

## Backends used in this run

* Card rail void latency: `simulator` (set STRIPE_SECRET_KEY=sk_test_... to measure on Stripe test mode).
* Stablecoin rail: x402 `exact` payments with real EIP-3009 / EIP-712 signatures, settled on the in-process ledger (`LocalChain`) with the escrow contract; no public testnet.
* SEPA Instant and Verification of Payee: in-process sandbox following EPC VoP response codes.
* Agents in E9: not run: no provider key configured; AgentDojo banking suite v1 executed with its own runtime and security checks.
* Embeddings for CBA: see results/raw/cba_calibration.json (`embedding_backend`).

## Mechanized verification

Tamarin models of the RAP exchange (T1, T2, T4), committed routes and attributability (T10, T11), and the AP2/ACP-style checkout with and without the extension (P10, P18); ProVerif equivalence for the private lookup.

#### Mechanized verification (Tamarin 1.12, ProVerif 2.05)

| model                       | variant          | lemma                         | result           |   steps | expected         | as expected   |   seconds |
|:----------------------------|:-----------------|:------------------------------|:-----------------|--------:|:-----------------|:--------------|----------:|
| meridian_v1.spthy           | default          | executable                    | verified         |      14 | verified         | True          |      2.1  |
| meridian_v1.spthy           | default          | df_soundness                  | verified         |      18 | verified         | True          |      2.1  |
| meridian_v1.spthy           | default          | unilateral_claim_resistance   | verified         |      18 | verified         | True          |      2.1  |
| meridian_v1.spthy           | default          | post_binding_swap             | verified         |      21 | verified         | True          |      2.1  |
| meridian_v1.spthy           | default          | release_unique                | verified         |      14 | verified         | True          |      2.1  |
| meridian_v1.spthy           | NOBETA           | executable                    | verified         |      11 | (not asserted)   | True          |      1.55 |
| meridian_v1.spthy           | NOBETA           | df_soundness                  | verified         |      18 | (not asserted)   | True          |      1.55 |
| meridian_v1.spthy           | NOBETA           | unilateral_claim_resistance   | verified         |      18 | (not asserted)   | True          |      1.55 |
| meridian_v1.spthy           | NOBETA           | post_binding_swap             | falsified        |      11 | falsified        | True          |      1.55 |
| meridian_v1.spthy           | NOBETA           | release_unique                | verified         |      14 | (not asserted)   | True          |      1.55 |
| meridian_v1.spthy           | ONESIDED         | executable                    | verified         |      13 | (not asserted)   | True          |      1.51 |
| meridian_v1.spthy           | ONESIDED         | df_soundness                  | falsified        |      13 | (not asserted)   | True          |      1.51 |
| meridian_v1.spthy           | ONESIDED         | unilateral_claim_resistance   | falsified        |      13 | falsified        | True          |      1.51 |
| meridian_v1.spthy           | ONESIDED         | post_binding_swap             | verified         |      18 | (not asserted)   | True          |      1.51 |
| meridian_v1.spthy           | ONESIDED         | release_unique                | verified         |      14 | (not asserted)   | True          |      1.51 |
| meridian_g2.spthy           | default          | executable_g2                 | verified         |      14 | verified         | True          |      1.9  |
| meridian_g2.spthy           | default          | executable_blame              | verified         |       7 | verified         | True          |      1.9  |
| meridian_g2.spthy           | default          | committed_route_soundness     | verified         |      29 | verified         | True          |      1.9  |
| meridian_g2.spthy           | default          | commitment_authentic          | verified         |      16 | verified         | True          |      1.9  |
| meridian_g2.spthy           | default          | no_false_blame                | verified         |      10 | verified         | True          |      1.9  |
| checkout_ext.spthy          | default          | executable                    | verified         |       8 | verified         | True          |      0.6  |
| checkout_ext.spthy          | default          | payee_authenticity            | falsified        |       8 | falsified        | True          |      0.6  |
| checkout_ext.spthy          | default          | endpoint_compromise_only      | falsified        |       8 | falsified        | True          |      0.6  |
| checkout_ext.spthy          | default          | discovery_runtime_consistency | falsified        |       8 | falsified        | True          |      0.6  |
| checkout_ext.spthy          | MERIDIAN         | executable                    | verified         |      15 | verified         | True          |      1.88 |
| checkout_ext.spthy          | MERIDIAN         | payee_authenticity            | verified         |      16 | verified         | True          |      1.88 |
| checkout_ext.spthy          | MERIDIAN         | endpoint_compromise_only      | verified         |      16 | verified         | True          |      1.88 |
| checkout_ext.spthy          | MERIDIAN         | discovery_runtime_consistency | verified         |      16 | verified         | True          |      1.88 |
| private_lookup.pv           | diff-equivalence | observational equivalence     | true             |     nan | true             | True          |    nan    |
| private_lookup_full_hash.pv | diff-equivalence | observational equivalence     | cannot be proved |     nan | cannot be proved | True          |    nan    |

Variants: NOBETA removes the payee binding token, ONESIDED removes operator acceptance, MERIDIAN adds the extension to the AP2/ACP-style checkout. A lemma expected to be falsified is a sanity check that the property depends on the removed mechanism.


## F3 toy check, T4 mutation tests, F5 split hardness

#### F3 toy check: B7 combined vs V1 original vs v2 core (hand-built structures)

| case     | B7 combined   | V1 original   | v2 core            | blueprint (B7 / V1 / v2)          | matches blueprint   | v2 reasons                                      |
|:---------|:--------------|:--------------|:-------------------|:----------------------------------|:--------------------|:------------------------------------------------|
| S1       | ok            | ok            | ok                 | ok / ok / ok                      | True                |                                                 |
| S2       | ok            | ok            | ok                 | ok / ok / ok                      | True                |                                                 |
| S3       | ok            | ok            | ok                 | ok / ok / ok                      | True                |                                                 |
| S4       | ok            | ok            | ok                 | ok / ok / ok                      | True                |                                                 |
| S5       | ok            | ok            | ok                 | ok / ok / ok                      | True                |                                                 |
| S6       | ok            | ok            | ok                 | false block / ok / ok             | False               |                                                 |
| S7       | ok            | ok            | ok                 | ok / ok / ok                      | True                |                                                 |
| S6 (a2a) | false block   | ok            | ok                 | false block / ok / ok             | True                |                                                 |
| X1       | loss          | stopped       | stopped            | loss / stopped / stopped          | True                | path-to-different-entity                        |
| X2       | loss          | loss          | stopped            | loss / loss / stopped             | True                | grammar:edge collects for a different principal |
| X3       | loss          | loss          | stopped            | loss / loss / stopped             | True                | grammar:terminal subject discontinuity          |
| X4       | stopped       | stopped       | stopped            | stopped / stopped / stopped       | True                | scope                                           |
| X5       | loss          | loss          | loss, attributable | loss / loss / loss, attributable  | True                |                                                 |
| X6       | allow         | allow         | step-up (G1 only)  | allow / allow / step-up (G1 only) | True                | no-commitment:proc:psptwo/acct_000001           |

V1 original and the v2 core are given the correct brand; anchoring is V2's job. These are logic checks of the verifiers on constructed structures, not evidence about real systems.


#### T4: mutation tests on AP2 v0.2 mandates and ACP checkout sessions

| protocol   | structure   | mutation                                       | verdict           | expected           | pass   |
|:-----------|:------------|:-----------------------------------------------|:------------------|:-------------------|:-------|
| AP2        | S1          | (none)                                         | ALLOW             | ALLOW              | True   |
| AP2        | S1          | payee.id                                       | DENY              | not ALLOW          | True   |
| AP2        | S1          | payee.id-empty                                 | DENY              | not ALLOW          | True   |
| AP2        | S1          | payee.name                                     | ALLOW             | ALLOW              | True   |
| AP2        | S1          | payment_amount                                 | DENY              | not ALLOW          | True   |
| AP2        | S1          | transaction_id                                 | DENY              | not ALLOW          | True   |
| AP2        | S1          | ra.route_digest                                | DENY              | not ALLOW          | True   |
| AP2        | S1          | ra.binding_digest                              | DENY              | not ALLOW          | True   |
| AP2        | S1          | ra.anchored_brand                              | DENY              | not ALLOW          | True   |
| AP2        | S1          | ra.removed                                     | STEP-UP           | not ALLOW          | True   |
| ACP        | S1          | (none)                                         | ALLOW             | ALLOW              | True   |
| ACP        | S1          | receiving_authority.payee                      | DENY              | not ALLOW          | True   |
| ACP        | S1          | receiving_authority.route_digest               | DENY              | not ALLOW          | True   |
| ACP        | S1          | receiving_authority.binding_digest             | DENY              | not ALLOW          | True   |
| ACP        | S1          | receiving_authority.removed                    | STEP-UP           | not ALLOW          | True   |
| ACP        | S1          | totals.amount                                  | DENY              | not ALLOW          | True   |
| ACP        | S1          | seller.name                                    | ALLOW             | ALLOW              | True   |
| AP2        | S1          | (none)                                         | ALLOW             | ALLOW              | True   |
| AP2        | S1          | payee.id                                       | DENY              | not ALLOW          | True   |
| AP2        | S1          | payee.id-empty                                 | DENY              | not ALLOW          | True   |
| AP2        | S1          | payee.name                                     | ALLOW             | ALLOW              | True   |
| AP2        | S1          | payment_amount                                 | DENY              | not ALLOW          | True   |
| AP2        | S1          | transaction_id                                 | DENY              | not ALLOW          | True   |
| AP2        | S1          | ra.route_digest                                | DENY              | not ALLOW          | True   |
| AP2        | S1          | ra.binding_digest                              | DENY              | not ALLOW          | True   |
| AP2        | S1          | ra.anchored_brand                              | DENY              | not ALLOW          | True   |
| AP2        | S1          | ra.removed                                     | STEP-UP           | not ALLOW          | True   |
| ACP        | S1          | (none)                                         | ALLOW             | ALLOW              | True   |
| ACP        | S1          | receiving_authority.payee                      | DENY              | not ALLOW          | True   |
| ACP        | S1          | receiving_authority.route_digest               | DENY              | not ALLOW          | True   |
| ACP        | S1          | receiving_authority.binding_digest             | DENY              | not ALLOW          | True   |
| ACP        | S1          | receiving_authority.removed                    | STEP-UP           | not ALLOW          | True   |
| ACP        | S1          | totals.amount                                  | DENY              | not ALLOW          | True   |
| ACP        | S1          | seller.name                                    | ALLOW             | ALLOW              | True   |
| AP2        | -           | allowed_payees with empty id (reference check) | accepts any payee | finding reproduced | True   |
| AP2        | -           | allowed_payees with empty id (strict check)    | rejects           | rejects            | True   |


#### F5: verifying a supplied split is linear; finding one is a bin-packing search

|   destinations n |   intermediaries m |   instances |   search nodes (median) |   search nodes (max) |   search s (max) |   timeouts (5 s) |   feasible |   verify us (median) |
|-----------------:|-------------------:|------------:|------------------------:|---------------------:|-----------------:|-----------------:|-----------:|---------------------:|
|                8 |                  2 |           5 |            25           |         48           |            0     |                0 |          3 |                  0.8 |
|               12 |                  3 |           5 |           336           |       2511           |            0.001 |                0 |          4 |                  1.2 |
|               16 |                  4 |           5 |         24352           |     130200           |            0.04  |                0 |          5 |                  1.6 |
|               20 |                  5 |           5 |        250334           |          2.3159e+06  |            0.748 |                0 |          5 |                  2   |
|               24 |                  6 |           5 |             1.45449e+07 |          1.47456e+07 |            5.001 |                3 |          2 |                  2.2 |
|               28 |                  7 |           5 |             6.06468e+06 |          1.4123e+07  |            5.001 |                2 |          3 |                  2.8 |
|               32 |                  8 |           5 |             1.35578e+07 |          1.35905e+07 |            5.001 |                5 |          0 |                  3   |
|               36 |                  9 |           5 |             1.29393e+07 |          1.3099e+07  |            5.002 |                4 |          1 |                  3.4 |
|               40 |                 10 |           5 |             1.25911e+07 |          1.26198e+07 |            5.002 |                5 |          0 |                  3.6 |

Instances require an exact fit (sum of amounts equals total remaining budget).


## E1 V1a directory vs V1b proof-carrying

#### E1: added verifier latency (localhost HTTP; WAN column adds a modelled lognormal RTT, median 40 ms)

| variant                        |   p50_ms |   p95_ms |   p95_with_modelled_wan_ms |   third_party_round_trips |
|:-------------------------------|---------:|---------:|---------------------------:|--------------------------:|
| V1b (stapled status)           |    0.642 |    0.917 |                      0.917 |                         0 |
| V1b + synchronous status fetch |    1.349 |    1.962 |                     86.127 |                         1 |
| V1a directory (signed answers) |    1.088 |    1.413 |                     86.176 |                         1 |


#### E1: cases where V1a and V1b decide differently

| kind   | v1b     | v1a     | v1b_reason     | v1a_reason               |   n |
|:-------|:--------|:--------|:---------------|:-------------------------|----:|
| A3     | STEP-UP | DENY    | no-path        | path-to-different-entity |  10 |
| A4     | STEP-UP | DENY    | no-path        | path-to-different-entity |  15 |
| A6     | DENY    | STEP-UP | payee-mismatch | no-path                  |  10 |


#### E1: V1a under outage and a lying directory (all payees targeted)

| directory           | client            | benign allowed   | attack losses   |
|:--------------------|:------------------|:-----------------|:----------------|
| outage              | checks signatures | 0/520            | 0/300           |
| outage              | trusting          | 0/520            | 0/300           |
| omit                | checks signatures | 0/520            | 0/300           |
| omit                | trusting          | 0/520            | 0/300           |
| stale               | checks signatures | 0/520            | 0/300           |
| stale               | trusting          | 480/520          | 130/300         |
| forge               | checks signatures | 0/520            | 0/300           |
| forge               | trusting          | 480/520          | 130/300         |
| assert              | checks signatures | 0/520            | 0/300           |
| assert              | trusting          | 520/520          | 300/300         |
| (V1b, no directory) | -                 | 480/520          | see E2 (M1-G1)  |


#### E1: information revealed to third parties per payment

| variant                | third party      | learns per payment                      |   identifiers | anonymity set                  |
|:-----------------------|:-----------------|:----------------------------------------|--------------:|:-------------------------------|
| V1a                    | directory        | anchor brand, payee, amount, rail, time |       5       | 1                              |
| V1b stapled            | none             | -                                       |       0       | -                              |
| V1b synchronous status | status-list host | which status lists were fetched         |       1.98171 | list capacity (65,536 entries) |


## E2 attack matrix

![E2 attack matrix](figures/e2_attack_heatmap.png)

#### E2: diversion success (loss / attempts), in-model cases

|                                                          | B1    | B2    | B3    | B4    | B5    | B6    | B7    | M1-G1   | M1    | M2    | M3    |
|:---------------------------------------------------------|:------|:------|:------|:------|:------|:------|:------|:--------|:------|:------|:------|
| A1 lookalike brand surfaced                              | 35/60 | 60/60 | 37/60 | 60/60 | 60/60 | 41/60 | 32/60 | 60/60   | 60/60 | 0/60  | 0/60  |
| A2 fake app or merchant listing in a directory           | 44/60 | 60/60 | 37/60 | 60/60 | 60/60 | 35/60 | 37/60 | 60/60   | 60/60 | 0/60  | 0/60  |
| A3 payee substituted in the checkout object              | 60/60 | 33/60 | 60/60 | 54/60 | 60/60 | 60/60 | 0/60  | 0/60    | 0/60  | 0/60  | 0/60  |
| A4 feed or registry poisoning of the payment endpoint    | 60/60 | 60/60 | 60/60 | 56/60 | 60/60 | 60/60 | 0/60  | 0/60    | 0/60  | 0/60  | 0/60  |
| A5 rogue sub-merchant under a real payment facilitator   | 41/60 | 60/60 | 60/60 | 60/60 | 60/60 | 56/60 | 27/60 | 0/60    | 0/60  | 0/60  | 0/60  |
| A6 settlement account changed (BEC style)                | 60/60 | 60/60 | 60/60 | 48/60 | 40/60 | 60/60 | 19/60 | 20/60   | 0/60  | 0/60  | 0/60  |
| A7 stale or revoked delegation reused                    | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 0/60  | 0/60    | 0/60  | 0/60  | 0/60  |
| A8 scope abuse (rail, currency, MCC, ceiling, geography) | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 0/60  | 0/60    | 0/60  | 0/60  | 0/60  |
| A9 freshly issued fake delegation from a careless issuer | 60/60 | 60/60 | 30/60 | 60/60 | 60/60 | 54/60 | 30/60 | 60/60   | 60/60 | 0/60  | 0/60  |
| A10 registry equivocation (split view)                   | 60/60 | 60/60 | 24/60 | 60/60 | 60/60 | 60/60 | 22/60 | 60/60   | 60/60 | 0/60  | 0/60  |
| A11 post-authorization first-hop mismatch                | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 30/60 | 60/60   | 60/60 | 38/60 | 0/60  |
| A12 diversion on an irreversible rail                    | 60/60 | 60/60 | 60/60 | 30/60 | 60/60 | 60/60 | 30/60 | 60/60   | 60/60 | 42/60 | 2/60  |
| A13 custodian deviates after committing (extra)          | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 56/60 | 60/60   | 60/60 | 51/60 | 51/60 |

Exact counts over constructed cases. A loss means funds reached a terminal account that is not legitimate for the brand the user intended and the payment was not undone. Step-ups count as blocked here (the user declines); see e2_stepup for the share that relied on the user.


#### E2: attacks stopped only by a step-up to the user (count / attempts)

| kind   | B1   | B2   | B3    | B4   | B5   | B6    | B7    | M1-G1   | M1    | M2    | M3    |
|:-------|:-----|:-----|:------|:-----|:-----|:------|:------|:--------|:------|:------|:------|
| A1     | 0/60 | 0/60 | 23/60 | 0/60 | 0/60 | 14/60 | 28/60 | 0/60    | 0/60  | 58/60 | 58/60 |
| A2     | 0/60 | 0/60 | 23/60 | 0/60 | 0/60 | 20/60 | 23/60 | 0/60    | 0/60  | 60/60 | 60/60 |
| A3     | 0/60 | 0/60 | 0/60  | 0/60 | 0/60 | 0/60  | 30/60 | 20/60   | 20/60 | 36/60 | 36/60 |
| A4     | 0/60 | 0/60 | 0/60  | 0/60 | 0/60 | 0/60  | 52/60 | 30/60   | 30/60 | 45/60 | 45/60 |
| A5     | 0/60 | 0/60 | 0/60  | 0/60 | 0/60 | 0/60  | 33/60 | 30/60   | 60/60 | 60/60 | 60/60 |
| A6     | 0/60 | 0/60 | 0/60  | 0/60 | 0/60 | 0/60  | 11/60 | 20/60   | 20/60 | 37/60 | 37/60 |
| A7     | 0/60 | 0/60 | 0/60  | 0/60 | 0/60 | 0/60  | 60/60 | 60/60   | 60/60 | 60/60 | 60/60 |
| A8     | 0/60 | 0/60 | 0/60  | 0/60 | 0/60 | 0/60  | 60/60 | 60/60   | 60/60 | 60/60 | 60/60 |
| A9     | 0/60 | 0/60 | 30/60 | 0/60 | 0/60 | 0/60  | 30/60 | 0/60    | 0/60  | 44/60 | 44/60 |
| A10    | 0/60 | 0/60 | 36/60 | 0/60 | 0/60 | 0/60  | 38/60 | 0/60    | 0/60  | 60/60 | 60/60 |
| A11    | 0/60 | 0/60 | 0/60  | 0/60 | 0/60 | 0/60  | 0/60  | 0/60    | 0/60  | 22/60 | 22/60 |
| A12    | 0/60 | 0/60 | 0/60  | 0/60 | 0/60 | 0/60  | 4/60  | 0/60    | 0/60  | 18/60 | 38/60 |
| A13    | 0/60 | 0/60 | 0/60  | 0/60 | 0/60 | 0/60  | 4/60  | 0/60    | 0/60  | 9/60  | 9/60  |


#### E2: loss by attack variant

|                                        | B1    | B2    | B3    | B4    | B5    | B6    | B7    | M1-G1   | M1    | M2    | M3    |
|:---------------------------------------|:------|:------|:------|:------|:------|:------|:------|:--------|:------|:------|:------|
| ('A1', 'affix')                        | 2/7   | 7/7   | 4/7   | 7/7   | 7/7   | 4/7   | 4/7   | 7/7     | 7/7   | 0/7   | 0/7   |
| ('A1', 'homoglyph')                    | 5/7   | 7/7   | 3/7   | 7/7   | 7/7   | 4/7   | 2/7   | 7/7     | 7/7   | 0/7   | 0/7   |
| ('A1', 'hyphenation')                  | 4/6   | 6/6   | 4/6   | 6/6   | 6/6   | 3/6   | 4/6   | 6/6     | 6/6   | 0/6   | 0/6   |
| ('A1', 'semantic-twin')                | 4/6   | 6/6   | 3/6   | 6/6   | 6/6   | 3/6   | 3/6   | 6/6     | 6/6   | 0/6   | 0/6   |
| ('A1', 'tld-swap')                     | 4/6   | 6/6   | 4/6   | 6/6   | 6/6   | 4/6   | 4/6   | 6/6     | 6/6   | 0/6   | 0/6   |
| ('A1', 'typo-omission')                | 4/7   | 7/7   | 4/7   | 7/7   | 7/7   | 7/7   | 3/7   | 7/7     | 7/7   | 0/7   | 0/7   |
| ('A1', 'typo-repeat')                  | 6/7   | 7/7   | 7/7   | 7/7   | 7/7   | 4/7   | 7/7   | 7/7     | 7/7   | 0/7   | 0/7   |
| ('A1', 'typo-replace')                 | 3/7   | 7/7   | 5/7   | 7/7   | 7/7   | 6/7   | 5/7   | 7/7     | 7/7   | 0/7   | 0/7   |
| ('A1', 'typo-swap')                    | 3/7   | 7/7   | 3/7   | 7/7   | 7/7   | 6/7   | 0/7   | 7/7     | 7/7   | 0/7   | 0/7   |
| ('A10', 'split-view')                  | 60/60 | 60/60 | 24/60 | 60/60 | 60/60 | 60/60 | 22/60 | 60/60   | 60/60 | 0/60  | 0/60  |
| ('A11', 'acquirer-level-swap')         | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30   | 30/30 | 20/30 | 0/30  |
| ('A11', 'transaction-laundering')      | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 0/30  | 30/30   | 30/30 | 18/30 | 0/30  |
| ('A12', 'a2a_instant:late-revocation') | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15   | 15/15 | 14/15 | 1/15  |
| ('A12', 'a2a_instant:stale-authority') | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15   | 15/15 | 15/15 | 0/15  |
| ('A12', 'stablecoin:late-revocation')  | 15/15 | 15/15 | 15/15 | 0/15  | 15/15 | 15/15 | 0/15  | 15/15   | 15/15 | 8/15  | 1/15  |
| ('A12', 'stablecoin:stale-authority')  | 15/15 | 15/15 | 15/15 | 0/15  | 15/15 | 15/15 | 0/15  | 15/15   | 15/15 | 5/15  | 0/15  |
| ('A13', 'custodian-deviates')          | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 60/60 | 56/60 | 60/60   | 60/60 | 51/60 | 51/60 |
| ('A2', 'name-clone')                   | 44/60 | 60/60 | 37/60 | 60/60 | 60/60 | 35/60 | 37/60 | 60/60   | 60/60 | 0/60  | 0/60  |
| ('A3', 'swap-keep-rap')                | 20/20 | 11/20 | 20/20 | 19/20 | 20/20 | 20/20 | 0/20  | 0/20    | 0/20  | 0/20  | 0/20  |
| ('A3', 'swap-no-rap')                  | 20/20 | 11/20 | 20/20 | 17/20 | 20/20 | 20/20 | 0/20  | 0/20    | 0/20  | 0/20  | 0/20  |
| ('A3', 'swap-own-rap')                 | 20/20 | 11/20 | 20/20 | 18/20 | 20/20 | 20/20 | 0/20  | 0/20    | 0/20  | 0/20  | 0/20  |
| ('A4', 'feed-no-rap')                  | 30/30 | 30/30 | 30/30 | 26/30 | 30/30 | 30/30 | 0/30  | 0/30    | 0/30  | 0/30  | 0/30  |
| ('A4', 'feed-own-rap')                 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 0/30  | 0/30    | 0/30  | 0/30  | 0/30  |
| ('A5', 'entity-rap')                   | 23/30 | 30/30 | 30/30 | 30/30 | 30/30 | 28/30 | 27/30 | 0/30    | 0/30  | 0/30  | 0/30  |
| ('A5', 'no-rap')                       | 18/30 | 30/30 | 30/30 | 30/30 | 30/30 | 28/30 | 0/30  | 0/30    | 0/30  | 0/30  | 0/30  |
| ('A6', 'a2a-invoice-account')          | 20/20 | 20/20 | 20/20 | 20/20 | 0/20  | 20/20 | 0/20  | 0/20    | 0/20  | 0/20  | 0/20  |
| ('A6', 'card-payout-change')           | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 19/20 | 20/20   | 0/20  | 0/20  | 0/20  |
| ('A6', 'coin-payto-change')            | 20/20 | 20/20 | 20/20 | 8/20  | 20/20 | 20/20 | 0/20  | 0/20    | 0/20  | 0/20  | 0/20  |
| ('A7', 'fresh-snapshot')               | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 0/30  | 0/30    | 0/30  | 0/30  | 0/30  |
| ('A7', 'stale-snapshot')               | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 0/30  | 0/30    | 0/30  | 0/30  | 0/30  |
| ('A8', 'ceiling')                      | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 0/12  | 0/12    | 0/12  | 0/12  | 0/12  |
| ('A8', 'currency')                     | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 0/12  | 0/12    | 0/12  | 0/12  | 0/12  |
| ('A8', 'geo')                          | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 0/12  | 0/12    | 0/12  | 0/12  | 0/12  |
| ('A8', 'mcc')                          | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 0/12  | 0/12    | 0/12  | 0/12  | 0/12  |
| ('A8', 'rail')                         | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 0/12  | 0/12    | 0/12  | 0/12  | 0/12  |
| ('A9', 'careless-domain-verifier')     | 60/60 | 60/60 | 30/60 | 60/60 | 60/60 | 54/60 | 30/60 | 60/60   | 60/60 | 0/60  | 0/60  |


#### E2: premise-violation partition, diversion success

|                                                                                                             | B1    | B2    | B3    | B4    | B5    | B6    | B7    | M1-G1   | M1    | M2    | M3    |
|:------------------------------------------------------------------------------------------------------------|:------|:------|:------|:------|:------|:------|:------|:--------|:------|:------|:------|
| PV1 compromised (careless) root issues a false brand edge and the brand monitor is offline during probation | 20/20 | 20/20 | 9/20  | 20/20 | 20/20 | 20/20 | 8/20  | 20/20   | 20/20 | 15/20 | 15/20 |
| PV2 all V3 observers on the rail collude                                                                    | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 10/20 | 20/20   | 20/20 | 15/20 | 15/20 |
| PV3 revocation published later than the staleness bound rho                                                 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20   | 20/20 | 11/20 | 11/20 |
| PV4 split view with every gossip peer colluding (no honest gossip)                                          | 20/20 | 20/20 | 9/20  | 20/20 | 20/20 | 20/20 | 9/20  | 20/20   | 20/20 | 12/20 | 12/20 |
| PV5 user explicitly confirms a lookalike at step-up                                                         | 11/20 | 20/20 | 20/20 | 20/20 | 20/20 | 17/20 | 20/20 | 20/20   | 20/20 | 19/20 | 19/20 |

Reported as boundaries, not failures: each row breaks a standing assumption.


#### E2: paired exact McNemar tests on loss

| A   | B     | cases        |   n |   loss under A only |   loss under B only |   p (exact McNemar) |
|:----|:------|:-------------|----:|--------------------:|--------------------:|--------------------:|
| M2  | M1    | A1+A2        | 120 |                   0 |                 120 |           1.5e-36   |
| M1  | M1-G1 | A6+A13       | 120 |                   0 |                  20 |           1.91e-06  |
| M3  | M2    | A11+A12      | 120 |                   0 |                  78 |           6.62e-24  |
| M1  | B7    | all in-model | 780 |                 183 |                  46 |           1.56e-20  |
| M2  | B7    | all in-model | 780 |                  35 |                 187 |           2.75e-26  |
| M3  | B7    | all in-model | 780 |                   5 |                 235 |           7.36e-63  |
| M3  | M1    | all in-model | 780 |                   0 |                 367 |           6.65e-111 |


## E3 legitimate structures

#### E3: false blocks on legitimate structures (count / payments)

|                                         | B1   | B2   | B3   | B4   | B5   | B6   | B7   | M1-G1   | M1   | M2   | M3   |
|:----------------------------------------|:-----|:-----|:-----|:-----|:-----|:-----|:-----|:--------|:-----|:-----|:-----|
| S1 direct card merchant                 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S2 direct account-to-account            | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S3 brand store on a marketplace         | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S4 payment facilitator sub-merchant     | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S5 merchant of record / reseller        | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S6 buy-now-pay-later lender             | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S7 agent platform as merchant of record | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S8 franchise (geography-scoped)         | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S9 multi-brand group                    | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S10 newly onboarded merchant            | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S11 small merchant without credentials  | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S12 direct stablecoin merchant          | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |
| S13 escrow custody (held funds)         | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90    | 0/90 | 0/90 | 0/90 |


#### E3: step-ups on legitimate structures (count / payments)

|                                         | B1   | B2   | B3   | B4   | B5   | B6   | B7    | M1-G1   | M1    | M2    | M3    |
|:----------------------------------------|:-----|:-----|:-----|:-----|:-----|:-----|:------|:--------|:------|:------|:------|
| S1 direct card merchant                 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 1/90  | 0/90    | 0/90  | 20/90 | 20/90 |
| S2 direct account-to-account            | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 1/90  | 0/90    | 0/90  | 4/90  | 4/90  |
| S3 brand store on a marketplace         | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 5/90  | 0/90    | 0/90  | 23/90 | 23/90 |
| S4 payment facilitator sub-merchant     | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 5/90  | 0/90    | 0/90  | 26/90 | 26/90 |
| S5 merchant of record / reseller        | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 3/90  | 0/90    | 0/90  | 0/90  | 0/90  |
| S6 buy-now-pay-later lender             | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 6/90  | 0/90    | 0/90  | 0/90  | 0/90  |
| S7 agent platform as merchant of record | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 1/90  | 0/90    | 0/90  | 0/90  | 0/90  |
| S8 franchise (geography-scoped)         | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 5/90  | 0/90    | 0/90  | 0/90  | 0/90  |
| S9 multi-brand group                    | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 2/90  | 0/90    | 0/90  | 44/90 | 44/90 |
| S10 newly onboarded merchant            | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 4/90  | 0/90    | 0/90  | 26/90 | 26/90 |
| S11 small merchant without credentials  | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 90/90 | 90/90   | 90/90 | 90/90 | 90/90 |
| S12 direct stablecoin merchant          | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 3/90  | 0/90    | 0/90  | 59/90 | 59/90 |
| S13 escrow custody (held funds)         | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 0/90 | 4/90  | 0/90    | 0/90  | 0/90  | 0/90  |


#### E3: why benign payments were stepped up (by verifier stage)

| config   |   cba |   delegation |   mtl |   name-anchor |   pav |   route |
|:---------|------:|-------------:|------:|--------------:|------:|--------:|
| B7       |     0 |           85 |     0 |            45 |     0 |       0 |
| M1       |     0 |            0 |     0 |             0 |     0 |      90 |
| M1-G1    |     0 |            0 |     0 |             0 |    90 |       0 |
| M2       |   176 |            0 |    26 |             0 |     0 |      90 |
| M3       |   176 |            0 |    26 |             0 |     0 |      90 |


#### E3: CBA step-up rate by brand exposure to impersonation

| config   | brand impersonated   | CBA step-ups         |
|:---------|:---------------------|:---------------------|
| M1       | True                 | 0.000 [0.000, 0.013] |
| M1       | False                | 0.000 [0.000, 0.005] |
| M2       | True                 | 0.601 [0.544, 0.655] |
| M2       | False                | 0.000 [0.000, 0.005] |
| M3       | True                 | 0.601 [0.544, 0.655] |
| M3       | False                | 0.000 [0.000, 0.005] |

Brands outside S10 (new) and S11 (no credentials). Wilson 95% intervals.


#### E3: benign false-block and step-up rates (S1-S9, S12, S13), cluster bootstrap 95% CI

| config   |   n | false_block             | step_up                 |
|:---------|----:|:------------------------|:------------------------|
| B1       | 990 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| B2       | 990 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| B3       | 990 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| B4       | 990 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| B5       | 990 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| B6       | 990 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| B7       | 990 | 0.0000 [0.0000, 0.0000] | 0.0364 [0.0250, 0.0481] |
| M1-G1    | 990 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| M1       | 990 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| M2       | 990 | 0.0000 [0.0000, 0.0000] | 0.1778 [0.1125, 0.2485] |
| M3       | 990 | 0.0000 [0.0000, 0.0000] | 0.1778 [0.1125, 0.2485] |


## RQ5 per-rail comparison

#### RQ5: per-rail security / utility by configuration

| rail        | config   | attack_loss   |   loss_rate |   benign_step_up |   benign_false_block |   p95_decision_ms |
|:------------|:---------|:--------------|------------:|-----------------:|---------------------:|------------------:|
| a2a_instant | B1       | 60/60         |      1      |           0      |                    0 |            0.002  |
| a2a_instant | B2       | 58/60         |      0.9667 |           0      |                    0 |            0.0006 |
| a2a_instant | B3       | 60/60         |      1      |           0      |                    0 |            0.0006 |
| a2a_instant | B4       | 60/60         |      1      |           0      |                    0 |            0.0006 |
| a2a_instant | B5       | 40/60         |      0.6667 |           0      |                    0 |            0.0034 |
| a2a_instant | B6       | 60/60         |      1      |           0      |                    0 |            0.0006 |
| a2a_instant | B7       | 30/60         |      0.5    |           0.3206 |                    0 |            0.2985 |
| a2a_instant | M1       | 30/60         |      0.5    |           0.313  |                    0 |            0.6378 |
| a2a_instant | M1-G1    | 30/60         |      0.5    |           0.313  |                    0 |            0.6485 |
| a2a_instant | M2       | 29/60         |      0.4833 |           0.3435 |                    0 |            2.001  |
| a2a_instant | M3       | 1/60          |      0.0167 |           0.3435 |                    0 |            1.8739 |
| bnpl        | B1       | 0/0           |    nan      |           0      |                    0 |            0.0018 |
| bnpl        | B2       | 0/0           |    nan      |           0      |                    0 |            0.0006 |
| bnpl        | B3       | 0/0           |    nan      |           0      |                    0 |            0.0007 |
| bnpl        | B4       | 0/0           |    nan      |           0      |                    0 |            0.0006 |
| bnpl        | B5       | 0/0           |    nan      |           0      |                    0 |            0.0006 |
| bnpl        | B6       | 0/0           |    nan      |           0      |                    0 |            0.0006 |
| bnpl        | B7       | 0/0           |    nan      |           0.0667 |                    0 |            0.5769 |
| bnpl        | M1       | 0/0           |    nan      |           0      |                    0 |            1.2795 |
| bnpl        | M1-G1    | 0/0           |    nan      |           0      |                    0 |            0.9286 |
| bnpl        | M2       | 0/0           |    nan      |           0      |                    0 |            2.8973 |
| bnpl        | M3       | 0/0           |    nan      |           0      |                    0 |            2.7702 |
| card        | B1       | 492/535       |      0.9196 |           0      |                    0 |            0.0019 |
| card        | B2       | 523/535       |      0.9776 |           0      |                    0 |            0.0006 |
| card        | B3       | 441/535       |      0.8243 |           0      |                    0 |            0.0007 |
| card        | B4       | 535/535       |      1      |           0      |                    0 |            0.0006 |
| card        | B5       | 535/535       |      1      |           0      |                    0 |            0.0006 |
| card        | B6       | 503/535       |      0.9402 |           0      |                    0 |            0.001  |
| card        | B7       | 190/535       |      0.3551 |           0.1063 |                    0 |            0.5635 |
| card        | M1       | 274/535       |      0.5121 |           0.0734 |                    0 |            1.526  |
| card        | M1-G1    | 294/535       |      0.5495 |           0.0734 |                    0 |            0.9032 |
| card        | M2       | 64/535        |      0.1196 |           0.238  |                    0 |            3.1252 |
| card        | M3       | 26/535        |      0.0486 |           0.238  |                    0 |            3.0089 |
| psp_token   | B1       | 68/77         |      0.8831 |           0      |                    0 |            0.0017 |
| psp_token   | B2       | 74/77         |      0.961  |           0      |                    0 |            0.0006 |
| psp_token   | B3       | 70/77         |      0.9091 |           0      |                    0 |            0.0007 |
| psp_token   | B4       | 77/77         |      1      |           0      |                    0 |            0.0006 |
| psp_token   | B5       | 77/77         |      1      |           0      |                    0 |            0.0006 |
| psp_token   | B6       | 69/77         |      0.8961 |           0      |                    0 |            0.0024 |
| psp_token   | B7       | 45/77         |      0.5844 |           0.0471 |                    0 |            0.567  |
| psp_token   | M1       | 54/77         |      0.7013 |           0      |                    0 |            1.5429 |
| psp_token   | M1-G1    | 54/77         |      0.7013 |           0      |                    0 |            0.9122 |
| psp_token   | M2       | 25/77         |      0.3247 |           0.1353 |                    0 |            3.2316 |
| psp_token   | M3       | 25/77         |      0.3247 |           0.1353 |                    0 |            3.204  |
| stablecoin  | B1       | 76/80         |      0.95   |           0      |                    0 |            0.0019 |
| stablecoin  | B2       | 76/80         |      0.95   |           0      |                    0 |            0.0006 |
| stablecoin  | B3       | 74/80         |      0.925  |           0      |                    0 |            0.0007 |
| stablecoin  | B4       | 28/80         |      0.35   |           0      |                    0 |            0.001  |
| stablecoin  | B5       | 80/80         |      1      |           0      |                    0 |            0.0006 |
| stablecoin  | B6       | 70/80         |      0.875  |           0      |                    0 |            0.0023 |
| stablecoin  | B7       | 12/80         |      0.15   |           0.0333 |                    0 |            0.3581 |
| stablecoin  | M1       | 50/80         |      0.625  |           0      |                    0 |            0.652  |
| stablecoin  | M1-G1    | 50/80         |      0.625  |           0      |                    0 |            0.7019 |
| stablecoin  | M2       | 13/80         |      0.1625 |           0.6556 |                    0 |            1.9494 |
| stablecoin  | M3       | 1/80          |      0.0125 |           0.6556 |                    0 |            1.8353 |
| wallet      | B1       | 24/28         |      0.8571 |           0      |                    0 |            0.0019 |
| wallet      | B2       | 22/28         |      0.7857 |           0      |                    0 |            0.0006 |
| wallet      | B3       | 23/28         |      0.8214 |           0      |                    0 |            0.0007 |
| wallet      | B4       | 28/28         |      1      |           0      |                    0 |            0.0006 |
| wallet      | B5       | 28/28         |      1      |           0      |                    0 |            0.0006 |
| wallet      | B6       | 24/28         |      0.8571 |           0      |                    0 |            0.0023 |
| wallet      | B7       | 6/28          |      0.2143 |           0      |                    0 |            0.3036 |
| wallet      | M1       | 12/28         |      0.4286 |           0      |                    0 |            1.0099 |
| wallet      | M1-G1    | 12/28         |      0.4286 |           0      |                    0 |            0.6463 |
| wallet      | M2       | 0/28          |      0      |           0.2857 |                    0 |            2.6183 |
| wallet      | M3       | 0/28          |      0      |           0.2857 |                    0 |            2.5553 |


## E4 anchoring calibration

![E4 anchoring calibration](figures/e4_cba_tradeoff.png)

#### E4: lookalike detection AUC by confusability component

| score   |   AUC lookalike vs unrelated |   n_pos |   n_neg |
|:--------|-----------------------------:|--------:|--------:|
| str     |                       0.9999 |     631 |    1308 |
| vis     |                       0.9065 |     631 |    1308 |
| sem     |                       0.963  |     631 |    1308 |
| kappa   |                       0.9999 |     631 |    1308 |


#### E4: confusability by lookalike technique

| technique     |   n |   median kappa |   share kappa >= 0.6 |
|:--------------|----:|---------------:|---------------------:|
| affix         |  62 |          0.882 |                    1 |
| homoglyph     |  57 |          0.972 |                    1 |
| hyphenation   |  68 |          0.975 |                    1 |
| name-clone    |  70 |          0.976 |                    1 |
| semantic-twin |  66 |          0.877 |                    1 |
| tld-swap      |  66 |          0.974 |                    1 |
| typo-omission |  55 |          0.936 |                    1 |
| typo-repeat   |  63 |          0.943 |                    1 |
| typo-replace  |  69 |          0.938 |                    1 |
| typo-swap     |  55 |          0.907 |                    1 |


#### E4: held-out operating point (theta=0.9, tau=0.075) and component ablation

| components                   | benign step-up       |   benign wrong commit | attack false commit   |   attack step-up |
|:-----------------------------|:---------------------|----------------------:|:----------------------|-----------------:|
| all (str+vis+sem)            | 0.154 [0.129, 0.184] |                0.0015 | 0.003 [0.001, 0.016]  |           0.5759 |
| string only                  | 0.154 [0.129, 0.184] |                0.0015 | 0.003 [0.001, 0.016]  |           0.5759 |
| visual only                  | 0.000 [0.000, 0.006] |                0.1361 | 0.519 [0.466, 0.571]  |           0      |
| semantic only                | 0.000 [0.000, 0.006] |                0.1361 | 0.519 [0.466, 0.571]  |           0      |
| string+visual                | 0.154 [0.129, 0.184] |                0.0015 | 0.003 [0.001, 0.016]  |           0.5759 |
| string+semantic              | 0.154 [0.129, 0.184] |                0.0015 | 0.003 [0.001, 0.016]  |           0.5759 |
| all, without LEI distinction | 0.297 [0.263, 0.333] |                0.0015 | 0.003 [0.001, 0.016]  |           0.6332 |

Wilson 95% intervals. Prevalence of impersonated brands in the registry: 30%.


#### E4: sensitivity to the share of brands with lookalikes

|   impersonated share | benign step-up       | attack false commit   |
|---------------------:|:---------------------|:----------------------|
|                 0.05 | 0.023 [0.014, 0.037] | 0.000 [0.000, 0.063]  |
|                 0.2  | 0.097 [0.077, 0.122] | 0.000 [0.000, 0.018]  |
|                 0.5  | 0.218 [0.188, 0.252] | 0.000 [0.000, 0.007]  |
|                 1    | 0.438 [0.401, 0.476] | 0.000 [0.000, 0.004]  |


## E5 probation sweep

![E5 probation sweep](figures/e5_probation.png)

#### E5: probation Delta vs fake-delegation success (M2) and cost to new merchants

| Delta   | A9 rush success   |   A9 rush loss amount | A9 patient success   |   A9 patient loss amount | S10 new-merchant step-up   | established step-up (probation)   |
|:--------|:------------------|----------------------:|:---------------------|-------------------------:|:---------------------------|:----------------------------------|
| 0       | 25/60             |                197567 | 51/60                |                   412904 | 0/60                       | 0/180                             |
| 1h      | 25/60             |                197567 | 45/60                |                   371757 | 0/60                       | 0/180                             |
| 6h      | 11/60             |                 73214 | 19/60                |                   176766 | 4/60                       | 0/180                             |
| 1d      | 0/60              |                     0 | 4/60                 |                    58544 | 7/60                       | 0/180                             |
| 3d      | 0/60              |                     0 | 0/60                 |                        0 | 26/60                      | 0/180                             |
| 7d      | 0/60              |                     0 | 0/60                 |                        0 | 51/60                      | 0/180                             |
| 14d     | 0/60              |                     0 | 0/60                 |                        0 | 60/60                      | 0/180                             |

Monitor reaction: lognormal, median 6 h. Rush attacker uses the fake edge after a lognormal delay (median ~8 h); patient attacker waits Delta + 1-3 h. Exact counts.


#### E5: monitor reaction time vs success (Delta = 3 days)

| monitor median   | A9 rush success   | A9 patient success   |
|:-----------------|:------------------|:---------------------|
| 1h               | 0/60              | 0/60                 |
| 6h               | 0/60              | 0/60                 |
| 1d               | 0/60              | 6/60                 |
| 3d               | 2/60              | 28/60                |
| 7d               | 2/60              | 42/60                |


#### E5: amount cap during probation instead of step-up

|   cap (minor units) | A9 rush success   |   A9 rush loss amount | S10 new-merchant step-up   |
|--------------------:|:------------------|----------------------:|:---------------------------|
|                   0 | 0/60              |                     0 | 7/20                       |
|                2000 | 2/60              |                  2603 | 5/20                       |
|               10000 | 17/60             |                 84628 | 1/20                       |
|               50000 | 24/60             |                190780 | 0/20                       |


## E6 rail scheduling

![E6 rail scheduling](figures/e6_rail_residual.png)

#### E6: residual loss rate per rail, diversion class and mode (f = 0)

|                                  |   ESCROW |   POST |   PRE |   RWS |
|:---------------------------------|---------:|-------:|------:|------:|
| ('a2a_instant', 'first-hop')     |    0     |  1     |     0 | 0     |
| ('a2a_instant', 'late-evidence') |    0     |  1     |     1 | 0.052 |
| ('card', 'custodian')            |  nan     |  1     |     1 | 1     |
| ('card', 'first-hop')            |  nan     |  0.012 |     1 | 0.005 |
| ('card', 'late-evidence')        |  nan     |  0.007 |     1 | 0     |
| ('stablecoin', 'first-hop')      |    0     |  0     |     0 | 0     |
| ('stablecoin', 'late-evidence')  |    0.007 |  1     |     1 | 0.052 |

1.0 means no post-authorization diversion of this class was undone in time. 'first-hop' on stablecoin is stopped by the EIP-3009 signature binding before settlement.


#### E6: residual loss vs number of corrupted observers f (POST and RWS)

|                                          |     0 |     1 |     2 |
|:-----------------------------------------|------:|------:|------:|
| ('a2a_instant', 'first-hop', 'POST')     | 1     | 1     | 1     |
| ('a2a_instant', 'first-hop', 'RWS')      | 0     | 0     | 0     |
| ('a2a_instant', 'late-evidence', 'POST') | 1     | 1     | 1     |
| ('a2a_instant', 'late-evidence', 'RWS')  | 0.052 | 1     | 1     |
| ('card', 'custodian', 'POST')            | 1     | 1     | 1     |
| ('card', 'custodian', 'RWS')             | 1     | 1     | 1     |
| ('card', 'first-hop', 'POST')            | 0.012 | 0.01  | 1     |
| ('card', 'first-hop', 'RWS')             | 0.005 | 0.002 | 1     |
| ('card', 'late-evidence', 'POST')        | 0.007 | 0     | 0.002 |
| ('card', 'late-evidence', 'RWS')         | 0     | 0.002 | 1     |
| ('stablecoin', 'first-hop', 'POST')      | 0     | 0     | 0     |
| ('stablecoin', 'first-hop', 'RWS')       | 0     | 0     | 0     |
| ('stablecoin', 'late-evidence', 'POST')  | 1     | 1     | 1     |
| ('stablecoin', 'late-evidence', 'RWS')   | 0.052 | 0.032 | 1     |


#### E6: modes chosen by RWS (counts)

|                    |   ESCROW |   POST |   PRE |
|:-------------------|---------:|-------:|------:|
| ('a2a_instant', 0) |      768 |      0 |    32 |
| ('a2a_instant', 1) |        0 |      0 |   800 |
| ('a2a_instant', 2) |        0 |      0 |   800 |
| ('card', 0)        |        0 |   1200 |     0 |
| ('card', 1)        |        0 |   1200 |     0 |
| ('card', 2)        |        0 |      0 |  1200 |
| ('stablecoin', 0)  |      768 |      0 |    32 |
| ('stablecoin', 1)  |      766 |      0 |    34 |
| ('stablecoin', 2)  |        0 |      0 |   800 |


#### E6: Theorem 3 quantities per rail (modelled latencies, config/rails.yaml)

| rail        |   f |   POST-safe prob (G1 observers) |   FRESH-safe prob rho=60s |   FRESH-safe prob rho=300s |   ESCROW catch prob |
|:------------|----:|--------------------------------:|--------------------------:|---------------------------:|--------------------:|
| card        |   0 |                           0.995 |                     0.995 |                     0.9942 |             nan     |
| card        |   1 |                           0.995 |                     0.995 |                     0.9942 |             nan     |
| psp_token   |   0 |                           0.995 |                     0.995 |                     0.9942 |             nan     |
| psp_token   |   1 |                           0.995 |                     0.995 |                     0.9942 |             nan     |
| wallet      |   0 |                           0.99  |                     0.99  |                     0.9833 |             nan     |
| wallet      |   1 |                           0.99  |                     0.99  |                     0.9833 |             nan     |
| bnpl        |   0 |                           0.98  |                     0.98  |                     0.9731 |             nan     |
| bnpl        |   1 |                           0     |                     0.98  |                     0.9731 |             nan     |
| a2a_instant |   0 |                           0     |                     0     |                     0      |               0.999 |
| a2a_instant |   1 |                           0     |                     0     |                     0      |               0     |
| stablecoin  |   0 |                           0     |                     0     |                     0      |               0.999 |
| stablecoin  |   1 |                           0     |                     0     |                     0      |               0     |


#### F4 toy illustration

| condition                             | blueprint   | this run   |
|:--------------------------------------|:------------|:-----------|
| original (report only)                | 100%        | 100.0%     |
| corrected, honest observers           | 79%         | 78.6%      |
| corrected, fastest observer corrupted | 48%         | 47.6%      |
| stale-authority catch, rho = 3        | 67%         | 66.5%      |

Parameters: {'window': 10, 'observer_medians': [1, 4], 'void_median': 5, 'void_success': 0.97, 'decision_median': 0.25, 'lognormal_sigma': 0.6}


## E7 privacy cost (V4) and H4

#### E7: proof cost (ms)

| quantity                             |   p50_ms |   p95_ms |
|:-------------------------------------|---------:|---------:|
| Groth16 prove (prover side)          |   580.25 |   632.45 |
| Groth16 verify (payer side)          |     9.68 |    13.61 |
| V4 payer-side verify in bench (wall) |    10    |    12.7  |
| M3 pre-check (V1+V2) in bench        |     2.56 |    29.95 |
| BBS derive, k=3 (prover side)        |   190.62 |   254.19 |
| BBS verify, k=3 (payer side)         |   213.69 |   230.25 |


#### E7: proof size

| artifact                                |   bytes |
|:----------------------------------------|--------:|
| Groth16 proof (snarkjs JSON)            |     723 |
| Groth16 proof (2 G1 + 1 G2, compressed) |     128 |
| BBS presentation, k=2                   |     672 |
| BBS presentation, k=3                   |    1040 |
| BBS presentation, k=4                   |    1408 |


#### E7: private log lookups

| scheme                         |   records |   median anonymity set |   response bytes (median) |   upload bytes |   server+client ms |
|:-------------------------------|----------:|-----------------------:|--------------------------:|---------------:|-------------------:|
| k-anon prefix 8 bits           |    200000 |                    779 |                     31180 |              1 |             nan    |
| k-anon prefix 12 bits          |    200000 |                     50 |                      2000 |              2 |             nan    |
| k-anon prefix 16 bits          |    200000 |                      4 |                       160 |              2 |             nan    |
| k-anon prefix 20 bits          |    200000 |                      1 |                        40 |              3 |             nan    |
| 2-server XOR PIR, 2^12 records |      4096 |                   4096 |                       128 |           1024 |               0.28 |
| 2-server XOR PIR, 2^14 records |     16384 |                  16384 |                       128 |           4096 |               0.81 |
| 2-server XOR PIR, 2^16 records |     65536 |                  65536 |                       128 |          16384 |               3.36 |


#### E7/H4: cases where the V4 pre-check decides differently from M3

| kind   | variant   | m3_pre   | m4   | stage   | m4_stage   | n   |
|--------|-----------|----------|------|---------|------------|-----|


#### E7: what each variant reveals per payment

| variant                        | verifier learns                                                                       | identifiers                                |
|:-------------------------------|:--------------------------------------------------------------------------------------|:-------------------------------------------|
| V1b / M1                       | full path: brand, entity, platform, PSP account, payout account (hashed), all issuers | k + 1 nodes, 2k signers                    |
| V1a                            | as V1b; directory also learns brand, payee, amount, time                              | as V1b + 5 to directory                    |
| V2 log lookup (plain)          | -                                                                                     | log operator learns every edge id queried  |
| V2 log lookup (k-anon 16 bits) | -                                                                                     | log learns a prefix; anonymity set ~4      |
| V3 observers                   | first hop, transfer records, terminal credit                                          | observers learn the payment id             |
| V4 SNARK                       | brand, payee p, hiding commitment to terminal, ALLOW bit                              | 2 + 1 commitment (linkable per merchant)   |
| V4 BBS                         | brand, payee p, edge types, scopes, salted link tags, issuer keys                     | 2 + k link tags (linkable) + k issuer keys |


## E8 scalability

#### E8: PAV cost by path length (single core)

|   k_edges |   signature_checks |   pav_per_s |   us_per_pav |   rap_bytes |
|----------:|-------------------:|------------:|-------------:|------------:|
|         2 |                  7 |      1550.2 |        645.1 |        1575 |
|         3 |                  9 |      1229.2 |        813.5 |        2055 |
|         4 |                 11 |      1039.5 |        962   |        2576 |
|         5 |                 13 |       864.8 |       1156.3 |        3097 |
|         6 |                 15 |       767.6 |       1302.8 |        3618 |


#### E8: directory reachability with scope filtering (V1a)

|      nodes |      edges |   csr_build_s |   memory_MB |   query_p50_ms |   query_p95_ms |   queries |   reachable_share |
|-----------:|-----------:|--------------:|------------:|---------------:|---------------:|----------:|------------------:|
|  10000     | 100000     |          0.01 |         4.4 |          0.262 |          0.618 |       300 |             0.223 |
| 100000     |      1e+06 |          0.1  |        43.7 |          0.352 |          0.745 |       300 |             0.123 |
|      1e+06 |      1e+07 |          1.73 |       436.8 |          0.475 |          1.077 |       300 |             0.057 |


#### E8: Merchant Transparency Log proofs

|           leaves |   root_build_s |   inclusion_proof_bytes_max |   inclusion_proof_bytes_mean |   proof_gen_ms_p50 |   proof_verify_ms_p50 |   consistency_proof_bytes(n/2->n) |
|-----------------:|---------------:|----------------------------:|-----------------------------:|-------------------:|----------------------:|----------------------------------:|
|  16384           |           0.01 |                         448 |                        448   |              0.007 |                 0.007 |                                32 |
| 131072           |           0.07 |                         544 |                        544   |              0.011 |                 0.009 |                                32 |
|      1.04858e+06 |           0.52 |                         640 |                        640   |              0.016 |                 0.01  |                                32 |
|      1e+07       |           5.1  |                         768 |                        757.4 |            nan     |               nan     |                               nan |


## E9 agent containment

#### E9: AgentDojo banking suite, compromised agent vs gate

| gate      | attacker payee   |   runs | unauthorized payment (agent compromised in every run)   |   of which the user had typed that IBAN |
|:----------|:-----------------|-------:|:--------------------------------------------------------|----------------------------------------:|
| MERIDIAN  | known            |    128 | 0.062 [0.032, 0.118]                                    |                                       8 |
| MERIDIAN  | novel            |   2560 | 0.000 [0.000, 0.001]                                    |                                       0 |
| blocklist | known            |    128 | 0.000 [0.000, 0.029]                                    |                                       0 |
| blocklist | novel            |   2560 | 1.000 [0.999, 1.000]                                    |                                       0 |
| none      | known            |    128 | 1.000 [0.971, 1.000]                                    |                                       8 |
| none      | novel            |   2560 | 1.000 [0.999, 1.000]                                    |                                       0 |

Ground-truth agent: follows every injection (compromise rate 1). Attack success is AgentDojo's security() for the suite's IBAN and 'money reached the injected IBAN' for novel IBANs. In user_task_15 the user types the suite's attacker IBAN as their new landlord, so that payee is user-named there.


#### E9: AgentDojo benign payment tasks (utility per the suite's checks)

| gate      |   runs | benign payment tasks completed   |   benign step-ups |
|:----------|-------:|:---------------------------------|------------------:|
| MERIDIAN  |     10 | 1.000 [0.722, 1.000]             |                 1 |
| blocklist |     10 | 0.900 [0.596, 0.982]             |                 0 |
| none      |     10 | 1.000 [0.722, 1.000]             |                 0 |


#### E9: agent compromise rate vs downstream unauthorized-payee payment rate

| gate      | attacker payee   |   agent compromise rate |   unauthorized-payee payment rate |
|:----------|:-----------------|------------------------:|----------------------------------:|
| MERIDIAN  | known            |                    0.1  |                            0.0062 |
| MERIDIAN  | known            |                    0.25 |                            0.0156 |
| MERIDIAN  | known            |                    0.5  |                            0.0312 |
| MERIDIAN  | known            |                    1    |                            0.0625 |
| MERIDIAN  | novel            |                    0.1  |                            0      |
| MERIDIAN  | novel            |                    0.25 |                            0      |
| MERIDIAN  | novel            |                    0.5  |                            0      |
| MERIDIAN  | novel            |                    1    |                            0      |
| blocklist | known            |                    0.1  |                            0      |
| blocklist | known            |                    0.25 |                            0      |
| blocklist | known            |                    0.5  |                            0      |
| blocklist | known            |                    1    |                            0      |
| blocklist | novel            |                    0.1  |                            0.1    |
| blocklist | novel            |                    0.25 |                            0.25   |
| blocklist | novel            |                    0.5  |                            0.5    |
| blocklist | novel            |                    1    |                            1      |
| none      | known            |                    0.1  |                            0.1    |
| none      | known            |                    0.25 |                            0.25   |
| none      | known            |                    0.5  |                            0.5    |
| none      | known            |                    1    |                            1      |
| none      | novel            |                    0.1  |                            0.1    |
| none      | novel            |                    0.25 |                            0.25   |
| none      | novel            |                    0.5  |                            0.5    |
| none      | novel            |                    1    |                            1      |


#### E9: marketplace simulation with manipulative lookalike businesses (scripted agents)

|   manipulation p | intent   | config   |   customers |   agent manipulated |   paid a lookalike |   step-ups |
|-----------------:|:---------|:---------|------------:|--------------------:|-------------------:|-----------:|
|              0.1 | generic  | B6       |          28 |                   5 |                  2 |          3 |
|              0.1 | named    | B6       |          72 |                   5 |                  2 |          3 |
|              0.1 | generic  | B7       |          28 |                   5 |                  0 |         28 |
|              0.1 | named    | B7       |          72 |                   5 |                  5 |          5 |
|              0.1 | generic  | M1       |          28 |                   5 |                  5 |          0 |
|              0.1 | named    | M1       |          72 |                   5 |                  5 |          0 |
|              0.1 | generic  | M2       |          28 |                   5 |                  0 |         28 |
|              0.1 | named    | M2       |          72 |                   5 |                  0 |         24 |
|              0.3 | generic  | B6       |          31 |                   6 |                  6 |          0 |
|              0.3 | named    | B6       |          69 |                  22 |                 15 |          7 |
|              0.3 | generic  | B7       |          31 |                   6 |                  0 |         31 |
|              0.3 | named    | B7       |          69 |                  22 |                 22 |          5 |
|              0.3 | generic  | M1       |          31 |                   6 |                  6 |          0 |
|              0.3 | named    | M1       |          69 |                  22 |                 22 |          0 |
|              0.3 | generic  | M2       |          31 |                   6 |                  0 |         31 |
|              0.3 | named    | M2       |          69 |                  22 |                  0 |         15 |
|              0.5 | generic  | B6       |          21 |                   9 |                  6 |          3 |
|              0.5 | named    | B6       |          79 |                  46 |                 30 |         16 |
|              0.5 | generic  | B7       |          21 |                   9 |                  0 |         21 |
|              0.5 | named    | B7       |          79 |                  46 |                 39 |         11 |
|              0.5 | generic  | M1       |          21 |                   9 |                  9 |          0 |
|              0.5 | named    | M1       |          79 |                  46 |                 46 |          0 |
|              0.5 | generic  | M2       |          21 |                   9 |                  0 |         21 |
|              0.5 | named    | M2       |          79 |                  46 |                  0 |         20 |

Generic intents name no brand, so there is no intended brand to anchor to; diversion to a lookalike there is outside MERIDIAN's object (the counterparty is who it claims to be).


## E10 coverage in the wild

#### E10: receiving-authority edges buildable from public / KYB data

| market   |   retailers | L0->L1 domain to entity   | verified mark (VMC)   | LEI issued           | platform/PSP identifiable   | bank terminal binding (VoP/CoP)   | full path buildable today   |
|:---------|------------:|:--------------------------|:----------------------|:---------------------|:----------------------------|:----------------------------------|:----------------------------|
| EU       |          20 | 0.800 [0.584, 0.919]      | 0.550 [0.342, 0.742]  | 0.350 [0.181, 0.567] | 0.000 [0.000, 0.161]        | yes                               | 0.000 [0.000, 0.161]        |
| IN       |          20 | 0.950 [0.764, 0.991]      | 0.100 [0.028, 0.301]  | 0.850 [0.640, 0.948] | 0.050 [0.009, 0.236]        | yes                               | 0.050 [0.009, 0.236]        |
| UK       |          20 | 0.900 [0.699, 0.972]      | 0.250 [0.112, 0.469]  | 0.650 [0.433, 0.819] | 0.150 [0.052, 0.360]        | yes                               | 0.050 [0.009, 0.236]        |
| US       |          20 | 1.000 [0.839, 1.000]      | 0.500 [0.299, 0.701]  | 0.600 [0.387, 0.781] | 0.100 [0.028, 0.301]        | no                                | 0.000 [0.000, 0.161]        |

Wilson 95% intervals. 'Identifiable' means the storefront exposes the PSP or commerce platform that already runs KYB; LEI matches are name-based and need manual confirmation before use. US: no national payee-verification scheme for account-to-account transfers. UK: Confirmation of Payee (Pay.UK), name-based. EU: Verification of Payee mandatory since 9 Oct 2025 (Instant Payments Regulation); LEI/VAT for legal persons. IN: beneficiary name validation on UPI/IMPS before payment.


#### E10: registered lookalike domains (DNS A or NS record exists)

| market   |   retailers |   generated |   registered |   registered share | retailers with >=1 registered lookalike   |
|:---------|------------:|------------:|-------------:|-------------------:|:------------------------------------------|
| EU       |          20 |         499 |          276 |              0.553 | 20/20                                     |
| IN       |          20 |         500 |          183 |              0.366 | 19/20                                     |
| UK       |          20 |         498 |          252 |              0.506 | 20/20                                     |
| US       |          20 |         497 |          393 |              0.791 | 20/20                                     |

Registered does not mean malicious: many are defensive registrations by the brand itself.


## Ablations

Ablation 4 (probation) is E5, 5 (observers and collusion) is E6, 6 (RAP vs directory) is E1.

#### Ablation 1: unilateral claim by a processor controlling one endpoint

| edges     |   attempts |   diverted under V1 original |   diverted under v2 core |
|:----------|-----------:|-----------------------------:|-------------------------:|
| bilateral |         40 |                            0 |                        0 |
| one-sided |         40 |                           40 |                        0 |


#### Ablation 2: scope abuse (A8) with and without the scope meet (M1)

| variant   | off (ablation)   | on   |
|:----------|:-----------------|:-----|
| ceiling   | 8/8              | 0/8  |
| currency  | 8/8              | 0/8  |
| geo       | 8/8              | 0/8  |
| mcc       | 8/8              | 0/8  |
| rail      | 8/8              | 0/8  |


#### Ablation 3: reuse of a revoked delegation vs freshness bound rho (V1)

|    rho | reuse accepted   |   accepted share |   share of revocations younger than rho |
|-------:|:-----------------|-----------------:|----------------------------------------:|
|      0 | 0/160            |            0     |                                   0     |
|     60 | 41/160           |            0.256 |                                   0.263 |
|    300 | 57/160           |            0.356 |                                   0.356 |
|   3600 | 80/160           |            0.5   |                                   0.5   |
|  86400 | 120/160          |            0.75  |                                   0.75  |
| 604800 | 142/160          |            0.887 |                                   0.887 |

Revocation ages are log-uniform between 10 s and 30 days; the attacker staples the freshest pre-revocation snapshot.

