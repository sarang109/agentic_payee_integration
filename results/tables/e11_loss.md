### E11: rational custodians that steal, reference workload (30 payments in flight)

|                                        | 0.3     | 0.4     | 0.5     | 0.6    | 0.7    | 0.8    | 0.9    | 1.0   |
|:---------------------------------------|:--------|:--------|:--------|:-------|:-------|:-------|:-------|:------|
| ('provisioned', 'floor', 'off')        | 144/180 | 3/180   | 0/180   | 0/180  | 0/180  | 0/180  | 0/180  | 0/180 |
| ('provisioned', 'floor', 'on')         | 0/180   | 0/180   | 0/180   | 0/180  | 0/180  | 0/180  | 0/180  | 0/180 |
| ('provisioned', 'optimistic', 'off')   | 144/180 | 123/180 | 86/180  | 33/180 | 11/180 | 2/180  | 0/180  | 0/180 |
| ('provisioned', 'optimistic', 'on')    | 134/180 | 105/180 | 55/180  | 19/180 | 6/180  | 0/180  | 0/180  | 0/180 |
| ('provisioned', 'oracle', 'off')       | 144/180 | 123/180 | 86/180  | 33/180 | 11/180 | 2/180  | 0/180  | 0/180 |
| ('provisioned', 'oracle', 'on')        | 0/180   | 0/180   | 0/180   | 0/180  | 0/180  | 0/180  | 0/180  | 0/180 |
| ('unprovisioned', 'floor', 'off')      | 152/180 | 131/180 | 108/180 | 89/180 | 63/180 | 38/180 | 14/180 | 0/180 |
| ('unprovisioned', 'floor', 'on')       | 0/180   | 0/180   | 0/180   | 0/180  | 0/180  | 0/180  | 0/180  | 0/180 |
| ('unprovisioned', 'optimistic', 'off') | 152/180 | 131/180 | 108/180 | 89/180 | 63/180 | 38/180 | 14/180 | 0/180 |
| ('unprovisioned', 'optimistic', 'on')  | 95/180  | 69/180  | 44/180  | 15/180 | 5/180  | 0/180  | 0/180  | 0/180 |
| ('unprovisioned', 'oracle', 'off')     | 152/180 | 131/180 | 108/180 | 89/180 | 63/180 | 38/180 | 14/180 | 0/180 |
| ('unprovisioned', 'oracle', 'on')      | 0/180   | 0/180   | 0/180   | 0/180  | 0/180  | 0/180  | 0/180  | 0/180 |

Exact counts over simulated custodians. Provisioned: bond sized so the cap is 1.5 x mean exposure at the rule's q_hat. q is an input, swept from 0.3 to 1, not a measurement. Simulation of an economic model; the numbers say nothing about any deployed custodian.
