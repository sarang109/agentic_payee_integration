### E6: Theorem 3 quantities per rail (modelled latencies, config/rails.yaml)

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
