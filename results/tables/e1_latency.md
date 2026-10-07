### E1: added verifier latency (localhost HTTP; WAN column adds a modelled lognormal RTT, median 40 ms)

| variant                        |   p50_ms |   p95_ms |   p95_with_modelled_wan_ms |   third_party_round_trips |
|:-------------------------------|---------:|---------:|---------------------------:|--------------------------:|
| V1b (stapled status)           |    0.647 |    0.929 |                      0.929 |                         0 |
| V1b + synchronous status fetch |    1.326 |    1.93  |                     86.128 |                         1 |
| V1a directory (signed answers) |    1.074 |    1.405 |                     86.019 |                         1 |
