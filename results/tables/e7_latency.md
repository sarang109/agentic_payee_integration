### E7: proof cost (ms)

| quantity                             |   p50_ms |   p95_ms |
|:-------------------------------------|---------:|---------:|
| Groth16 prove (prover side)          |   580.25 |   632.45 |
| Groth16 verify (payer side)          |     9.68 |    13.61 |
| V4 payer-side verify in bench (wall) |    10    |    12.7  |
| M3 pre-check (V1+V2) in bench        |     2.56 |    29.95 |
| BBS derive, k=3 (prover side)        |   190.62 |   254.19 |
| BBS verify, k=3 (payer side)         |   213.69 |   230.25 |
