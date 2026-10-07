### E6: source of every timing input (measured or modelled)

| rail        | quantity                                                             | source                                                                                        |
|:------------|:---------------------------------------------------------------------|:----------------------------------------------------------------------------------------------|
| card        | reversibility window W_r                                             | modelled (config/rails.yaml)                                                                  |
| card        | observer latencies                                                   | modelled (config/rails.yaml)                                                                  |
| card        | decision latency                                                     | modelled (config/rails.yaml)                                                                  |
| card        | void latency and success                                             | measured: stripe-test-mode (archived measurement of 2026-10-07T02:32:18Z), n = 30, p50 0.40 s |
| psp_token   | reversibility window W_r                                             | modelled (config/rails.yaml)                                                                  |
| psp_token   | observer latencies                                                   | modelled (config/rails.yaml)                                                                  |
| psp_token   | decision latency                                                     | modelled (config/rails.yaml)                                                                  |
| psp_token   | void / recall latency and success                                    | modelled (config/rails.yaml)                                                                  |
| wallet      | reversibility window W_r                                             | modelled (config/rails.yaml)                                                                  |
| wallet      | observer latencies                                                   | modelled (config/rails.yaml)                                                                  |
| wallet      | decision latency                                                     | modelled (config/rails.yaml)                                                                  |
| wallet      | void / recall latency and success                                    | modelled (config/rails.yaml)                                                                  |
| bnpl        | reversibility window W_r                                             | modelled (config/rails.yaml)                                                                  |
| bnpl        | observer latencies                                                   | modelled (config/rails.yaml)                                                                  |
| bnpl        | decision latency                                                     | modelled (config/rails.yaml)                                                                  |
| bnpl        | void / recall latency and success                                    | modelled (config/rails.yaml)                                                                  |
| a2a_instant | reversibility window W_r                                             | modelled (config/rails.yaml)                                                                  |
| a2a_instant | observer latencies                                                   | modelled (config/rails.yaml)                                                                  |
| a2a_instant | decision latency                                                     | modelled (config/rails.yaml)                                                                  |
| a2a_instant | void / recall latency and success                                    | modelled (config/rails.yaml)                                                                  |
| stablecoin  | reversibility window W_r                                             | modelled (config/rails.yaml)                                                                  |
| stablecoin  | observer latencies                                                   | modelled (config/rails.yaml)                                                                  |
| stablecoin  | decision latency                                                     | modelled (config/rails.yaml)                                                                  |
| stablecoin  | void / recall latency and success                                    | modelled (config/rails.yaml)                                                                  |
| stablecoin  | chain receipt after settlement (context, not used in the simulation) | measured on Base Sepolia, n = 37, p50 0.82 s (modelled chain_receipt median: 2 s)             |
