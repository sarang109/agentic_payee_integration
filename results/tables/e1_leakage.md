### E1: information revealed to third parties per payment

| variant                | third party      | learns per payment                      |   identifiers | anonymity set                  |
|:-----------------------|:-----------------|:----------------------------------------|--------------:|:-------------------------------|
| V1a                    | directory        | anchor brand, payee, amount, rail, time |       5       | 1                              |
| V1b stapled            | none             | -                                       |       0       | -                              |
| V1b synchronous status | status-list host | which status lists were fetched         |       1.98171 | list capacity (65,536 entries) |
