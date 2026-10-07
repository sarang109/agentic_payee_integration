### E11: hold-time threshold T* at exposure = 1.5 x mean (days)

| population    | rule       |   q |   share unbounded |   share infeasible |   median T* (days, finite) |   share with hold <= T* |
|:--------------|:-----------|----:|------------------:|-------------------:|---------------------------:|------------------------:|
| provisioned   | oracle     | 0.3 |             0.165 |              0     |                      2.15  |                   1     |
| provisioned   | oracle     | 0.4 |             0.225 |              0     |                      2.535 |                   1     |
| provisioned   | oracle     | 0.5 |             0.3   |              0     |                      4.069 |                   1     |
| provisioned   | oracle     | 0.6 |             0.37  |              0     |                     11.247 |                   1     |
| provisioned   | oracle     | 0.7 |             0.44  |              0     |                     16.948 |                   1     |
| provisioned   | oracle     | 0.8 |             0.535 |              0     |                     20.318 |                   1     |
| provisioned   | oracle     | 0.9 |             0.63  |              0     |                     21.755 |                   1     |
| provisioned   | oracle     | 1   |             1     |              0     |                    nan     |                   1     |
| provisioned   | floor      | 0.3 |             0.165 |              0     |                      2.15  |                   1     |
| provisioned   | floor      | 0.4 |             0.225 |              0     |                     21.046 |                   1     |
| provisioned   | floor      | 0.5 |             0.3   |              0     |                     27.58  |                   1     |
| provisioned   | floor      | 0.6 |             0.37  |              0     |                     31.262 |                   1     |
| provisioned   | floor      | 0.7 |             0.44  |              0     |                     34.991 |                   1     |
| provisioned   | floor      | 0.8 |             0.535 |              0     |                     32.709 |                   1     |
| provisioned   | floor      | 0.9 |             0.63  |              0     |                     30.595 |                   1     |
| provisioned   | floor      | 1   |             1     |              0     |                    nan     |                   1     |
| provisioned   | optimistic | 0.3 |             0.165 |              0.755 |                    348.474 |                   0.245 |
| provisioned   | optimistic | 0.4 |             0.225 |              0.585 |                    141.737 |                   0.41  |
| provisioned   | optimistic | 0.5 |             0.3   |              0     |                      2.552 |                   0.68  |
| provisioned   | optimistic | 0.6 |             0.37  |              0     |                     11.247 |                   0.89  |
| provisioned   | optimistic | 0.7 |             0.44  |              0     |                     16.948 |                   0.965 |
| provisioned   | optimistic | 0.8 |             0.535 |              0     |                     20.318 |                   1     |
| provisioned   | optimistic | 0.9 |             0.63  |              0     |                     21.755 |                   1     |
| provisioned   | optimistic | 1   |             1     |              0     |                    nan     |                   1     |
| unprovisioned | -          | 0.3 |             0.165 |              0.79  |                    179.114 |                   0.21  |
| unprovisioned | -          | 0.4 |             0.225 |              0.655 |                     28.497 |                   0.33  |
| unprovisioned | -          | 0.5 |             0.3   |              0.51  |                     26.002 |                   0.435 |
| unprovisioned | -          | 0.6 |             0.37  |              0.38  |                     20.095 |                   0.6   |
| unprovisioned | -          | 0.7 |             0.44  |              0.235 |                     12.739 |                   0.715 |
| unprovisioned | -          | 0.8 |             0.535 |              0.115 |                     10.443 |                   0.825 |
| unprovisioned | -          | 0.9 |             0.63  |              0.015 |                     13     |                   0.965 |
| unprovisioned | -          | 1   |             1     |              0     |                    nan     |                   1     |

unbounded: margin and franchise alone deter; infeasible: even immediate release is not enough for this bond. Provisioned rows use the bond for the named rule.
