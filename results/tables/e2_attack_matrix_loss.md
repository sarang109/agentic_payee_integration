### E2: diversion success (loss / attempts), in-model cases

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
