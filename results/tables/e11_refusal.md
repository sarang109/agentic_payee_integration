### E11: refusal rate on legitimate payments, reference workload (30 payments in flight)

|                                 |    0.3 |    0.4 |    0.5 |    0.6 |    0.7 |    0.8 |    0.9 |    1.0 |
|:--------------------------------|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|
| ('provisioned', 'floor')        | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 |
| ('provisioned', 'optimistic')   | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 |
| ('provisioned', 'oracle')       | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 | 0.0116 |
| ('unprovisioned', 'floor')      | 0.4602 | 0.4602 | 0.4602 | 0.4602 | 0.4602 | 0.4602 | 0.4602 | 0.4602 |
| ('unprovisioned', 'optimistic') | 0.3465 | 0.3465 | 0.3465 | 0.3465 | 0.3465 | 0.3465 | 0.3465 | 0.3465 |
| ('unprovisioned', 'oracle')     | 0.4602 | 0.4057 | 0.369  | 0.3554 | 0.3484 | 0.3465 | 0.3464 | 0.3464 |

Pooled over custodians; cluster bootstrap by custodian in e11_refusal.csv. Target at most 0.05. For the provisioned population the cap is the same at every q, so the refusal rate does not depend on q; what q changes is the bond required (e11_bond). q is an input, swept from 0.3 to 1, not a measurement. Simulation of an economic model; the numbers say nothing about any deployed custodian.
