### RQ5 (exploratory): security versus friction per rail

| rail        | config   | attack loss   |   loss rate |   benign step-up | on the frontier   |
|:------------|:---------|:--------------|------------:|-----------------:|:------------------|
| a2a_instant | B7       | 30/60         |      0.5    |           0.3206 |                   |
| a2a_instant | M1       | 30/60         |      0.5    |           0.313  | yes               |
| a2a_instant | M2       | 29/60         |      0.4833 |           0.3435 |                   |
| a2a_instant | M3       | 1/60          |      0.0167 |           0.3435 | yes               |
| card        | B7       | 190/535       |      0.3551 |           0.1063 | yes               |
| card        | M1       | 274/535       |      0.5121 |           0.0734 | yes               |
| card        | M2       | 64/535        |      0.1196 |           0.238  |                   |
| card        | M3       | 26/535        |      0.0486 |           0.238  | yes               |
| psp_token   | B7       | 45/77         |      0.5844 |           0.0471 | yes               |
| psp_token   | M1       | 54/77         |      0.7013 |           0      | yes               |
| psp_token   | M2       | 25/77         |      0.3247 |           0.1353 | yes               |
| psp_token   | M3       | 25/77         |      0.3247 |           0.1353 | yes               |
| stablecoin  | B7       | 12/80         |      0.15   |           0.0333 | yes               |
| stablecoin  | M1       | 50/80         |      0.625  |           0      | yes               |
| stablecoin  | M2       | 13/80         |      0.1625 |           0.6556 |                   |
| stablecoin  | M3       | 1/80          |      0.0125 |           0.6556 | yes               |
| wallet      | B7       | 6/28          |      0.2143 |           0      | yes               |
| wallet      | M1       | 12/28         |      0.4286 |           0      |                   |
| wallet      | M2       | 0/28          |      0      |           0.2857 | yes               |
| wallet      | M3       | 0/28          |      0      |           0.2857 | yes               |

Not a pre-registered analysis. A configuration is on the frontier when no other configuration has both lower or equal loss and lower or equal benign step-up, with one strictly lower. Rails with no attack cases are omitted.
