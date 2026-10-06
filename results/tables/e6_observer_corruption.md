### E6: residual loss vs number of corrupted observers f (POST and RWS)

|                                          |     0 |     1 |     2 |
|:-----------------------------------------|------:|------:|------:|
| ('a2a_instant', 'first-hop', 'POST')     | 1     | 1     | 1     |
| ('a2a_instant', 'first-hop', 'RWS')      | 0     | 0     | 0     |
| ('a2a_instant', 'late-evidence', 'POST') | 1     | 1     | 1     |
| ('a2a_instant', 'late-evidence', 'RWS')  | 0.047 | 1     | 1     |
| ('card', 'custodian', 'POST')            | 1     | 1     | 1     |
| ('card', 'custodian', 'RWS')             | 1     | 1     | 1     |
| ('card', 'first-hop', 'POST')            | 0     | 0     | 1     |
| ('card', 'first-hop', 'RWS')             | 0     | 0     | 1     |
| ('card', 'late-evidence', 'POST')        | 0.002 | 0     | 0.002 |
| ('card', 'late-evidence', 'RWS')         | 0     | 0     | 1     |
| ('stablecoin', 'first-hop', 'POST')      | 0     | 0     | 0     |
| ('stablecoin', 'first-hop', 'RWS')       | 0     | 0     | 0     |
| ('stablecoin', 'late-evidence', 'POST')  | 1     | 1     | 1     |
| ('stablecoin', 'late-evidence', 'RWS')   | 0.032 | 0.042 | 1     |
