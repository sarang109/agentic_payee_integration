### Mechanized verification (Tamarin 1.12, ProVerif 2.05)

| model                       | variant          | lemma                         | result           |   steps | expected         | as expected   |   seconds |
|:----------------------------|:-----------------|:------------------------------|:-----------------|--------:|:-----------------|:--------------|----------:|
| meridian_v1.spthy           | default          | executable                    | verified         |      14 | verified         | True          |      2.1  |
| meridian_v1.spthy           | default          | df_soundness                  | verified         |      18 | verified         | True          |      2.1  |
| meridian_v1.spthy           | default          | unilateral_claim_resistance   | verified         |      18 | verified         | True          |      2.1  |
| meridian_v1.spthy           | default          | post_binding_swap             | verified         |      21 | verified         | True          |      2.1  |
| meridian_v1.spthy           | default          | release_unique                | verified         |      14 | verified         | True          |      2.1  |
| meridian_v1.spthy           | NOBETA           | executable                    | verified         |      11 | (not asserted)   | True          |      1.55 |
| meridian_v1.spthy           | NOBETA           | df_soundness                  | verified         |      18 | (not asserted)   | True          |      1.55 |
| meridian_v1.spthy           | NOBETA           | unilateral_claim_resistance   | verified         |      18 | (not asserted)   | True          |      1.55 |
| meridian_v1.spthy           | NOBETA           | post_binding_swap             | falsified        |      11 | falsified        | True          |      1.55 |
| meridian_v1.spthy           | NOBETA           | release_unique                | verified         |      14 | (not asserted)   | True          |      1.55 |
| meridian_v1.spthy           | ONESIDED         | executable                    | verified         |      13 | (not asserted)   | True          |      1.51 |
| meridian_v1.spthy           | ONESIDED         | df_soundness                  | falsified        |      13 | (not asserted)   | True          |      1.51 |
| meridian_v1.spthy           | ONESIDED         | unilateral_claim_resistance   | falsified        |      13 | falsified        | True          |      1.51 |
| meridian_v1.spthy           | ONESIDED         | post_binding_swap             | verified         |      18 | (not asserted)   | True          |      1.51 |
| meridian_v1.spthy           | ONESIDED         | release_unique                | verified         |      14 | (not asserted)   | True          |      1.51 |
| meridian_g2.spthy           | default          | executable_g2                 | verified         |      14 | verified         | True          |      1.9  |
| meridian_g2.spthy           | default          | executable_blame              | verified         |       7 | verified         | True          |      1.9  |
| meridian_g2.spthy           | default          | committed_route_soundness     | verified         |      29 | verified         | True          |      1.9  |
| meridian_g2.spthy           | default          | commitment_authentic          | verified         |      16 | verified         | True          |      1.9  |
| meridian_g2.spthy           | default          | no_false_blame                | verified         |      10 | verified         | True          |      1.9  |
| checkout_ext.spthy          | default          | executable                    | verified         |       8 | verified         | True          |      0.6  |
| checkout_ext.spthy          | default          | payee_authenticity            | falsified        |       8 | falsified        | True          |      0.6  |
| checkout_ext.spthy          | default          | endpoint_compromise_only      | falsified        |       8 | falsified        | True          |      0.6  |
| checkout_ext.spthy          | default          | discovery_runtime_consistency | falsified        |       8 | falsified        | True          |      0.6  |
| checkout_ext.spthy          | MERIDIAN         | executable                    | verified         |      15 | verified         | True          |      1.88 |
| checkout_ext.spthy          | MERIDIAN         | payee_authenticity            | verified         |      16 | verified         | True          |      1.88 |
| checkout_ext.spthy          | MERIDIAN         | endpoint_compromise_only      | verified         |      16 | verified         | True          |      1.88 |
| checkout_ext.spthy          | MERIDIAN         | discovery_runtime_consistency | verified         |      16 | verified         | True          |      1.88 |
| private_lookup.pv           | diff-equivalence | observational equivalence     | true             |     nan | true             | True          |    nan    |
| private_lookup_full_hash.pv | diff-equivalence | observational equivalence     | cannot be proved |     nan | cannot be proved | True          |    nan    |

Variants: NOBETA removes the payee binding token, ONESIDED removes operator acceptance, MERIDIAN adds the extension to the AP2/ACP-style checkout. A lemma expected to be falsified is a sanity check that the property depends on the removed mechanism.
