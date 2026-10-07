### F5: verifying a supplied split is linear; finding one is a bin-packing search

|   destinations n |   intermediaries m |   instances |   search nodes (median) |   search nodes (max) |   search s (max) |   timeouts (5 s) |   feasible |   verify us (median) |
|-----------------:|-------------------:|------------:|------------------------:|---------------------:|-----------------:|-----------------:|-----------:|---------------------:|
|                8 |                  2 |           5 |            25           |         48           |            0     |                0 |          3 |                  0.9 |
|               12 |                  3 |           5 |           336           |       2511           |            0.001 |                0 |          4 |                  1.2 |
|               16 |                  4 |           5 |         24352           |     130200           |            0.041 |                0 |          5 |                  1.7 |
|               20 |                  5 |           5 |        250334           |          2.3159e+06  |            0.831 |                0 |          5 |                  2   |
|               24 |                  6 |           5 |             1.42746e+07 |          1.44261e+07 |            5.001 |                3 |          2 |                  2.2 |
|               28 |                  7 |           5 |             6.06468e+06 |          1.39346e+07 |            5     |                2 |          3 |                  2.7 |
|               32 |                  8 |           5 |             1.35987e+07 |          1.36929e+07 |            5.001 |                5 |          0 |                  2.9 |
|               36 |                  9 |           5 |             1.29434e+07 |          1.32751e+07 |            5.001 |                4 |          1 |                  3.4 |
|               40 |                 10 |           5 |             1.23863e+07 |          1.24559e+07 |            5.002 |                5 |          0 |                  3.6 |

Instances require an exact fit (sum of amounts equals total remaining budget).
