### F5: verifying a supplied split is linear; finding one is a bin-packing search

|   destinations n |   intermediaries m |   instances |   search nodes (median) |   search nodes (max) |   search s (max) |   timeouts (5 s) |   feasible |   verify us (median) |
|-----------------:|-------------------:|------------:|------------------------:|---------------------:|-----------------:|-----------------:|-----------:|---------------------:|
|                8 |                  2 |           5 |            25           |         48           |            0     |                0 |          3 |                  0.8 |
|               12 |                  3 |           5 |           336           |       2511           |            0.001 |                0 |          4 |                  1.2 |
|               16 |                  4 |           5 |         24352           |     130200           |            0.04  |                0 |          5 |                  1.6 |
|               20 |                  5 |           5 |        250334           |          2.3159e+06  |            0.748 |                0 |          5 |                  2   |
|               24 |                  6 |           5 |             1.45449e+07 |          1.47456e+07 |            5.001 |                3 |          2 |                  2.2 |
|               28 |                  7 |           5 |             6.06468e+06 |          1.4123e+07  |            5.001 |                2 |          3 |                  2.8 |
|               32 |                  8 |           5 |             1.35578e+07 |          1.35905e+07 |            5.001 |                5 |          0 |                  3   |
|               36 |                  9 |           5 |             1.29393e+07 |          1.3099e+07  |            5.002 |                4 |          1 |                  3.4 |
|               40 |                 10 |           5 |             1.25911e+07 |          1.26198e+07 |            5.002 |                5 |          0 |                  3.6 |

Instances require an exact fit (sum of amounts equals total remaining budget).
