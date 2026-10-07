# Writing attacks for E12

You are asked to write at least 8 attacks against a payer-side payee check for
agentic payments. Read only this file. Please do not read the rest of the
repository, its results, or any code, until your attacks are delivered: the
point is that the attacks are not shaped by how the system or its benchmark
works. Do not run anything. If something here is unclear, say so in the
`narrative` of the attack that depends on it instead of guessing from the code.

## What is being protected

A shopping agent buys on a user's behalf. Before the payment is released, a
verifier running in the user's wallet or credential provider decides whether
the party that will receive the money is authorized to receive it for the
brand the user meant, and it may allow, deny, or ask the user to confirm. It
compares what the agent proposes with signed evidence. The agent is never
trusted.

**Principals.** The user states an intent ("buy running shoes from Brand X")
and holds the funding source. The shopping agent proposes a merchant, a cart
and a payee, and may be fully compromised. The receiving chain is: the brand,
its legal entity, a platform or merchant of record, a payment processor or
facilitator or acquirer, and the settlement account. Delegation issuers sign
the links of that chain: domain-control verifiers, legal-entity credential
issuers, platforms, payment processors, banks. Observers (a card issuer, the
payee's bank, a blockchain) can report what actually happened after the
payment is authorized. Log operators and brand monitors keep a public,
append-only record of who has been authorized to receive for a brand.

**Identity layers.** L0 the brand as displayed (name, logo, domain). L1 the
legal entity (a legal-entity identifier). L2 the merchant of record or the
platform account (a store ID, a marketplace seller ID). L3 the processing
account (a processor's connected account, a payment-facilitator sub-merchant,
an acquirer merchant ID). L4 the settlement endpoint (a bank account or a
wallet address).

**Rails.** card, psp_token (a processor's delegated token), wallet, a2a_instant
(instant account-to-account, effectively irreversible once sent), stablecoin
(irreversible unless escrowed), bnpl. Card payments can be voided before
capture; the others are harder to stop.

**Legitimate structures a victim may have.** S1 direct card merchant; S2 direct
account-to-account; S3 a brand's store on a marketplace; S4 a sub-merchant of a
payment facilitator; S5 merchant of record or reseller; S7 an agent platform
acting as merchant of record; S9 a multi-brand group; S12 direct stablecoin
merchant; S13 escrow or held-funds custody.

## The adversary

The attacker may control the shopping agent; publish lookalike brands, domains
and apps; register real companies; open real accounts at platforms and
payment processors; compromise a merchant's endpoint or product feed; take over
a merchant's processor dashboard; and compromise some observers. The attacker
cannot forge the signatures of honest issuers and cannot rewrite the public
log without being noticed. Attacks that need a broken assumption (a
compromised honest issuer, every observer colluding, the brand's monitor
offline) are allowed but must be marked `premise_violation: true`; they are
reported separately.

Out of scope: whether the product is what it claims to be, overcharging by a
legitimate merchant, non-delivery by a legitimate merchant, and attacks on the
user's own device.

## What to write

A JSON file with this shape. Each attack must be an attack in the strict
sense: if every check allowed the payment, the money would reach an account
that is not legitimately the brand's. Try to write attacks that you think the
verifier or a simple name/identity check would **miss**, and combine
capabilities where that helps; also include some you expect to be caught.

```json
{
  "schema": "meridian-e12/1",
  "attacks": [
    {
      "id": "A-01",
      "author": "author-1",
      "title": "short title",
      "narrative": "At least 40 characters: what the attacker does and why you think it works.",
      "victim": {"structure": "S3", "rail": "card"},
      "scenario": {"kind": "custodian_redirect"},
      "listing": {"manifest_valid": true, "curated": true},
      "user_words": "typo",
      "amount_cents": 25000,
      "checkout": {"swap_after_mandate": false},
      "premise_violation": false
    }
  ]
}
```

Required: `id` (unique), `author` (a stable label for you; use the same one on
every attack), `title`, `narrative`, `victim`, `scenario`. Optional:

* `listing`: booleans the platform or the user could see: `manifest_valid`
  (a signed merchant identity document exists for the displayed domain),
  `curated` (the platform's curation lists it), `known_bad` (it is on a
  blocklist), `looks_off` (an agent might find it suspicious).
* `user_words`: how the user typed the brand: `exact`, `lowercase`, `typo`,
  `abbreviated`.
* `amount_cents`: the payment amount (100 to 5,000,000).
* `checkout.swap_after_mandate`: the payee was changed after the user's signed
  authorization.
* `premise_violation`, `user_confirms_stepup`: as above, and whether the user
  confirms a prompt that asks them to check.

## Scenario kinds

Each kind fixes what the attacker does; you choose the victim and parameters.
Not every victim structure and rail is allowed for every kind (the validator
says which).

| kind | what happens | parameters |
|---|---|---|
| `lookalike` | The attacker publishes a lookalike brand with its own real company, account and valid credentials; the agent selects it | `technique`: homoglyph, typo-omission, typo-swap, typo-repeat, typo-replace, affix, tld-swap, hyphenation, name-clone, semantic-twin; `copy_logo` |
| `payee_swap` | The payee in the checkout object, feed or registry is replaced by the attacker's account | `evidence`: keep (the genuine merchant's proof is shown), own (the attacker's own valid proof), none; `channel`: checkout, feed, registry |
| `rogue_submerchant` | The attacker opens a sub-merchant account under a real payment facilitator and presents the brand | `evidence`: none, entity |
| `processor_payout_change` | After a dashboard takeover, the processor's payout account for the victim is changed to the attacker's account some hours before the payment | `hours_before` (1 to 72) |
| `custodian_redirect` | A real intermediary receives the money, as it should, and later sends it onward to the attacker's account | |
| `first_hop_mismatch` | A different processor account than the one the checkout named is the one that receives the authorization | `variant`: transaction-laundering, acquirer-swap |
| `revoked_delegation` | A former reseller's authorization was revoked; the attacker reuses it | `seconds_since_revocation`, `snapshot`: stale, fresh |
| `scope_abuse` | A real reseller is authorized for a narrower scope than the payment | `dimension`: geo, ceiling, currency, mcc, rail |
| `fresh_fake_delegation` | A careless issuer signs the attacker's claim to represent the brand; the attacker uses it | `wait`: rush, patient; `brand_monitor`: online, offline (offline is a premise violation) |
| `split_view` | The attacker shows a forged authorization only to the victim's verifier (different views of the public log) | |
| `irreversible_revocation` | An account's authorization was revoked recently (stale) or is revoked just after payment (late) | `variant`: stale-authority, late-revocation |

If none of these can express an attack you want to write, describe it in
plain words in a separate list called `unexpressible` in the JSON file (same
`author`, a title and a narrative). Those are not run. They are reviewed
before the freeze and, if several authors ask for the same thing, a kind is
added and listed in the changelog below.

## Delivery

Return one JSON file. Do not discuss the attacks with other authors before
delivery. Do not revise an attack after you have learned anything about how
the system behaves on it.

## Schema changelog

* `meridian-e12/1`: initial kinds as listed above.
