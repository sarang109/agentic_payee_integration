### X2/X3 reproduced on Stripe Connect test mode

| case                     | committed destination      | observed destination       | deviation detected   | breach certificate verifies   | transfer reversed   |   observe_s |   reversal_s | verifier decision                             |
|:-------------------------|:---------------------------|:---------------------------|:---------------------|:------------------------------|:--------------------|------------:|-------------:|:----------------------------------------------|
| X2 seller substitution   | ...sq9LHc                  | ...jzOwya                  | True                 | True                          | True                |       1.381 |        0.899 | nan                                           |
| X3 payout-account change | bank fingerprint ...mkZGG3 | bank fingerprint ...80OElh | True                 |                               |                     |     nan     |      nan     | DENY (grammar:terminal subject discontinuity) |
