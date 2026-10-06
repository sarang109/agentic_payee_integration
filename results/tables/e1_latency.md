### E1: added verifier latency (localhost HTTP; WAN column adds a modelled lognormal RTT, median 40 ms)

| variant                        |   p50_ms |   p95_ms |   p95_with_modelled_wan_ms |   third_party_round_trips |
|:-------------------------------|---------:|---------:|---------------------------:|--------------------------:|
| V1b (stapled status)           |    0.642 |    0.917 |                      0.917 |                         0 |
| V1b + synchronous status fetch |    1.349 |    1.962 |                     86.127 |                         1 |
| V1a directory (signed answers) |    1.088 |    1.413 |                     86.176 |                         1 |
