# Baselines and the specifications they model

Each baseline is a pre-authorization decision function in
`payeebench/configs.py`. The table says which published mechanism it
stands for, what the implementation checks, and where it simplifies the
source. A reviewer can use the last column to judge whether a baseline is
weaker than the real mechanism.

| Baseline | Source | What `configs.py` checks | Simplifications relative to the source |
|---|---|---|---|
| B1 platform curation | Assistant app and merchant directories (ACP feed onboarding, UCP Merchant Center) | Allows a listing the platform has curated, denies one it has not | Curation is a per-listing flag set by the generator (curated with some probability per attack); real onboarding checks are not modelled |
| B2 mandate payee binding | AP2 v0.2 Payment Mandate `allowed_payees`; Mastercard/Google Verifiable Intent | Denies when the payee was changed after the user signed the mandate | Does not model the AP2-17 fallback to display fields (arXiv 2609.00060, Sec. VI-B); the real verifier is weaker there, so B2 is if anything generous |
| B3 merchant identity attestation | AGTP Merchant Identity (draft-hood-agtp-merchant-identity-02) | Allows when the displayed domain has a valid merchant manifest, else step-up | Manifest validity is a flag; trust tiers and the 455 Counterparty Unverified flow are not modelled. AGTP leaves settlement out of scope, so B3 never checks the payee |
| B4 DID-to-wallet binding | PCAT principle P2 (arXiv 2607.21824) | On stablecoin, allows only a wallet listed in the merchant's did:web document; not applicable on other rails | did:web resolution and signature checks are reduced to set membership; a lookalike domain controls its own did:web, as in the source |
| B5 payee name check | EU Verification of Payee (EPC rulebook), UK Confirmation of Payee | On account-to-account, queries the sandbox bank with the name the checkout presents: MATCH allows, CLOSE_MATCH steps up, else deny | Uses the in-process VoP sandbox with EPC response codes; the name comes from the (possibly attacker-controlled) checkout, as in practice |
| B6 agent judgment plus lists | Agent-side heuristics; CAPE's blocklist finding | Denies blocklisted listings; steps up some listings that look off (fixed 30% detection) | Agent judgment is a seeded coin, not a model; E9 measures hosted-model judgment directly |
| B7 strongest combined | B2 + B3 + B4 + B5 with LEI, plus scoped delegation from the asserted entity, receipts, name anchoring | Manifest, name anchoring on legal or display name, mandate binding, did:web wallet on stablecoin, VoP against the LEI on account-to-account, scoped delegation chain from the asserted entity to the payee, receipt-based first-hop void on reversible rails | Built by this project from the components above rather than taken from a deployed system; it shares the generator with MERIDIAN (see limitations) |

## Not done

The publication plan asked for baselines "reimplemented from their specs".
The table above documents the mapping; it does not replace an independent
reimplementation. The closest external check is `e2_aip_external`, where
AIP-Bench fixes the attack scenario and PCAT's own claim (P2 stops wallet
substitution) is reproduced by B4 on the V9 scenario.
