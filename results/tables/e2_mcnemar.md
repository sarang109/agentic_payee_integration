### E2: paired exact McNemar tests on loss

| A   | B     | cases        |   n |   loss under A only |   loss under B only |   p (exact McNemar) |
|:----|:------|:-------------|----:|--------------------:|--------------------:|--------------------:|
| M2  | M1    | A1+A2        | 120 |                   0 |                 120 |           1.5e-36   |
| M1  | M1-G1 | A6+A13       | 120 |                   0 |                  20 |           1.91e-06  |
| M3  | M2    | A11+A12      | 120 |                   0 |                  78 |           6.62e-24  |
| M1  | B7    | all in-model | 780 |                 183 |                  46 |           1.56e-20  |
| M2  | B7    | all in-model | 780 |                  35 |                 187 |           2.75e-26  |
| M3  | B7    | all in-model | 780 |                   5 |                 235 |           7.36e-63  |
| M3  | M1    | all in-model | 780 |                   0 |                 367 |           6.65e-111 |
