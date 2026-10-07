### Gate A2: in-repo B2 against the AP2 SDK payee check (upstream commit e1ea56db72a6)

| group                               |   cases |   B2 denies |   upstream reports a violation |   agree |   B2 stricter |   upstream stricter |
|:------------------------------------|--------:|------------:|-------------------------------:|--------:|--------------:|--------------------:|
| G1 ids present                      |    1950 |          27 |                             27 |    1950 |             0 |                   0 |
| G2 ids empty, display fields copied |      27 |          27 |                              0 |       0 |            27 |                   0 |
| G3 ids empty, display fields differ |      27 |          27 |                             27 |      27 |             0 |                   0 |

Upstream code was run, not copied. G1 is the mapping documented in experiments/upstream_check.py. In G2-G4 the mandate carries no merchant id, so the upstream rule falls back to name and website; 'B2 stricter' counts cases where B2 denies and the SDK accepts. No upstream reference code exists for B5 (EPC Verification of Payee): the rulebook specifies messages and codes, not the matching; B5 stays re-specified.
