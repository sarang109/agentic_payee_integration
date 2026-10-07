### E9: hosted-model agent on benign tasks (utility per the suite's checks or the intended transfer)

| gate      | set                              |   runs | completed            | needed a step-up     |
|:----------|:---------------------------------|-------:|:---------------------|:---------------------|
| MERIDIAN  | all suite user tasks             |     48 | 0.479 [0.345, 0.617] | 0.083 [0.033, 0.196] |
| allowlist | all suite user tasks             |     48 | 0.479 [0.345, 0.617] | 0.125 [0.059, 0.247] |
| blocklist | all suite user tasks             |     48 | 0.500 [0.364, 0.636] | 0.000 [0.000, 0.074] |
| none      | all suite user tasks             |     48 | 0.521 [0.383, 0.655] | 0.000 [0.000, 0.074] |
| MERIDIAN  | suite user tasks with a payment  |     30 | 0.333 [0.192, 0.512] | 0.133 [0.053, 0.297] |
| allowlist | suite user tasks with a payment  |     30 | 0.333 [0.192, 0.512] | 0.200 [0.095, 0.373] |
| blocklist | suite user tasks with a payment  |     30 | 0.367 [0.219, 0.545] | 0.000 [0.000, 0.114] |
| none      | suite user tasks with a payment  |     30 | 0.367 [0.219, 0.545] | 0.000 [0.000, 0.114] |
| MERIDIAN  | synthetic: all                   |    100 | 1.000 [0.963, 1.000] | 0.250 [0.175, 0.343] |
| allowlist | synthetic: all                   |    100 | 1.000 [0.963, 1.000] | 0.750 [0.657, 0.825] |
| none      | synthetic: all                   |    100 | 1.000 [0.963, 1.000] | 0.000 [0.000, 0.037] |
| MERIDIAN  | synthetic: existing-counterparty |     25 | 1.000 [0.867, 1.000] | 0.000 [0.000, 0.133] |
| allowlist | synthetic: existing-counterparty |     25 | 1.000 [0.867, 1.000] | 0.000 [0.000, 0.133] |
| none      | synthetic: existing-counterparty |     25 | 1.000 [0.867, 1.000] | 0.000 [0.000, 0.133] |
| MERIDIAN  | synthetic: named-brand-attested  |     25 | 1.000 [0.867, 1.000] | 0.000 [0.000, 0.133] |
| allowlist | synthetic: named-brand-attested  |     25 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| none      | synthetic: named-brand-attested  |     25 | 1.000 [0.867, 1.000] | 0.000 [0.000, 0.133] |
| MERIDIAN  | synthetic: typed-new-iban        |     25 | 1.000 [0.867, 1.000] | 0.000 [0.000, 0.133] |
| allowlist | synthetic: typed-new-iban        |     25 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| none      | synthetic: typed-new-iban        |     25 | 1.000 [0.867, 1.000] | 0.000 [0.000, 0.133] |
| MERIDIAN  | synthetic: unattested-invoice    |     25 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| allowlist | synthetic: unattested-invoice    |     25 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| none      | synthetic: unattested-invoice    |     25 | 1.000 [0.867, 1.000] | 0.000 [0.000, 0.133] |

Measured with a hosted model; the user approves step-ups. Wilson 95% intervals.
