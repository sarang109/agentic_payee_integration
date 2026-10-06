### E4: held-out operating point (theta=0.9, tau=0.075) and component ablation

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
