### E7: private log lookups

| scheme                         |   records |   median anonymity set |   response bytes (median) |   upload bytes |   server+client ms |
|:-------------------------------|----------:|-----------------------:|--------------------------:|---------------:|-------------------:|
| k-anon prefix 8 bits           |    200000 |                    779 |                     31180 |              1 |             nan    |
| k-anon prefix 12 bits          |    200000 |                     50 |                      2000 |              2 |             nan    |
| k-anon prefix 16 bits          |    200000 |                      4 |                       160 |              2 |             nan    |
| k-anon prefix 20 bits          |    200000 |                      1 |                        40 |              3 |             nan    |
| 2-server XOR PIR, 2^12 records |      4096 |                   4096 |                       128 |           1024 |               0.24 |
| 2-server XOR PIR, 2^14 records |     16384 |                  16384 |                       128 |           4096 |               0.77 |
| 2-server XOR PIR, 2^16 records |     65536 |                  65536 |                       128 |          16384 |               3.47 |
