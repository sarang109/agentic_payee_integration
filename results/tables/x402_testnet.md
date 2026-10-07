### x402 exact payments on Base Sepolia through the public facilitator (measured on a public testnet)

| case                                                 |   runs | facilitator verify accepted   | settled on chain     | settle p50 / p95 s   | settle to receipt p50 / p95 s   | rejection reasons                                 |
|:-----------------------------------------------------|-------:|:------------------------------|:---------------------|:---------------------|:--------------------------------|:--------------------------------------------------|
| honest payment to merchant, run 1 (2026-10-07T02:46) |     20 | 1.000 [0.839, 1.000]          | 0.950 [0.764, 0.991] | 0.66 / 0.88          | 0.83 / 1.05                     | settlement errors: Missing or invalid parameters. |
| honest payment to merchant, run 2 (2026-10-07T02:50) |     20 | 1.000 [0.839, 1.000]          | 0.900 [0.699, 0.972] | 0.63 / 2.43          | 0.80 / 2.59                     | settlement errors: Missing or invalid parameters. |
| honest payment to merchant, all runs                 |     40 | 1.000 [0.912, 1.000]          | 0.925 [0.801, 0.974] | 0.65 / 1.63          | 0.82 / 1.79                     | settlement errors: Missing or invalid parameters. |
| recipient rewritten after signing                    |     20 | 0.000 [0.000, 0.161]          | -                    | -                    | -                               | invalid_exact_evm_signature                       |
| signed to attacker, presented as merchant            |     20 | 0.000 [0.000, 0.161]          | -                    | -                    | -                               | invalid_exact_evm_recipient_mismatch              |

All runs are kept, none are dropped. On-chain check: the payer held 20.00 test USDC before the first run and 19.63 after the last, a drop of exactly 37 settled payments, so failed settlements moved no funds. Latest run 2026-10-07T02:50:00Z, test USDC 0.01 per payment. Transaction hashes are in results/raw/x402_testnet_runs.csv. The escrow wrapper used by the ESCROW mode runs on the local ledger only.
