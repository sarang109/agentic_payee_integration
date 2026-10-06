### T4: mutation tests on AP2 v0.2 mandates and ACP checkout sessions

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
