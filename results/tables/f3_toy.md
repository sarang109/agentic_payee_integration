### F3 toy check: B7 combined vs V1 original vs v2 core (hand-built structures)

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

V1 original and the v2 core are given the correct brand; anchoring is V2's job. These are logic checks of the verifiers on constructed structures, not evidence about real systems. Correction to the blueprint's S6 row: B7 false-blocks the BNPL lender only when the lender is paid account-to-account, where B7's Verification of Payee against the brand's LEI fails because the lender owns the account (row 'S6 (a2a)'). On the card path B7 has no account-name check and allows the payment, so the blueprint's 'false block' for S6 holds only for account-to-account.
