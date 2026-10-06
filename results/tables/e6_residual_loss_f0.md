### E6: residual loss rate per rail, diversion class and mode (f = 0)

|                                  |   ESCROW |   POST |   PRE |   RWS |
|:---------------------------------|---------:|-------:|------:|------:|
| ('a2a_instant', 'first-hop')     |    0     |  1     |     0 | 0     |
| ('a2a_instant', 'late-evidence') |    0     |  1     |     1 | 0.052 |
| ('card', 'custodian')            |  nan     |  1     |     1 | 1     |
| ('card', 'first-hop')            |  nan     |  0.012 |     1 | 0.005 |
| ('card', 'late-evidence')        |  nan     |  0.007 |     1 | 0     |
| ('stablecoin', 'first-hop')      |    0     |  0     |     0 | 0     |
| ('stablecoin', 'late-evidence')  |    0.007 |  1     |     1 | 0.052 |

1.0 means no post-authorization diversion of this class was undone in time. 'first-hop' on stablecoin is stopped by the EIP-3009 signature binding before settlement.
