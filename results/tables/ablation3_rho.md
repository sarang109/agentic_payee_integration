### Ablation 3: reuse of a revoked delegation vs freshness bound rho (V1)

|    rho | reuse accepted   |   accepted share |   share of revocations younger than rho |
|-------:|:-----------------|-----------------:|----------------------------------------:|
|      0 | 0/160            |            0     |                                   0     |
|     60 | 41/160           |            0.256 |                                   0.263 |
|    300 | 57/160           |            0.356 |                                   0.356 |
|   3600 | 80/160           |            0.5   |                                   0.5   |
|  86400 | 120/160          |            0.75  |                                   0.75  |
| 604800 | 142/160          |            0.887 |                                   0.887 |

Revocation ages are log-uniform between 10 s and 30 days; the attacker staples the freshest pre-revocation snapshot.
