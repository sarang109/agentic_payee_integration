# Prior-art and differentiation notes

Searches run on 6-7 October 2026 for the checklist in the blueprint
(v2 core) and the publication plan. Each entry says what the work does,
how it relates to a MERIDIAN claim, and what the claim can safely say.
Entries marked *abstract only* were not read in full.

## Theorem 1 (non-observability) and the G0-G4 hierarchy

Search terms: "payment custody accountability", "payout destination
attestation", "accountable payment intermediaries", pre-authorization
evidence limits.

- **Chatzigiannis, Baldimtsi, Chalkias, "SoK: Auditability and
  Accountability in Distributed Payment Systems", IACR ePrint 2021/239**
  (*abstract only*). Systematizes auditability in ledger-based payment
  systems; lists dispute resolution between regulator and audited entity as
  open. No per-hop custodian commitments or pre-authorization evidence
  levels found in the abstract.
- **"Protocol-Embedded Compliance for Privacy-Preserving, Non-Custodial
  Digital Payments", arXiv 2608.17145** (*search snippet only*). Signed
  compliance certificates checked at the protocol level instead of by a
  custodian. Related in spirit (certificates replace trust in an
  intermediary); about compliance of assets, not destination of funds.
- No work found that states an evidence-to-guarantee hierarchy for payee
  integrity or the non-observability bound for discretionary custodians.

What the paper can say: the hierarchy and Theorem 1 are, to our search,
not stated elsewhere for payments; the argument itself is elementary
(indistinguishable pre-authorization views), and the paper should present
it as a framing result, not a deep theorem. Do not claim "first".

## Theorem 2 (attributability) and committed routes

- **Küsters, Truderung, Vogt, "Accountability: Definition and Relationship
  to Verifiability", ACM CCS 2010, pp. 526-535.** General accountability:
  a judge blames only misbehaving parties (fairness) and blames someone
  when the goal fails (completeness). Theorem 2 is an instance for payment
  custody: the breach certificate is the judge's evidence; T11 in Tamarin
  checks fairness (`no_false_blame`) and reachability (`executable_blame`).
  The paper should cite this and use its vocabulary.
- **Treitz, Künnemann, "Accountability in Certificate Transparency and
  Variants", arXiv 2609.11552 (CCS 2026)** (*abstract only*). Mechanized
  accountability for CT in the Dolev-Yao model; plain CT gives
  accountability only with an honest log; SCT auditing removes that
  dependency, gossip does not. Directly relevant to V2's transparency log
  (T5): MERIDIAN's log uses gossip, so the paper should not claim log
  accountability without an honest log, and should consider SCT-auditing
  style checks.
- **ACK-Pay receipts** (blueprint source list). Signed receipts naming
  payer, amount and recipient after the fact; no custodian commitments
  before authorization.
- **AGTP Merchant Identity, draft-hood-agtp-merchant-identity-02 (26 May
  2026).** Read: "It does not define payment credential handling,
  tokenization, authorization messages to card networks, or settlement."
  The -01 to -02 changes (Agent Identity Documents, `role: "merchant"`,
  trust-tier paths) add no payee or settlement binding;
  `accepted_payment_networks` stays informational.
- **Merchant Identity Assertions for Autonomous Commerce
  (draft-anders-merchant-identity-assertions-01)**: settlement listed as a
  non-goal (blueprint reading, 3 Oct 2026).

What the paper can say: binding merchant identity through custodians to a
terminal account (F3) is not covered by the identity drafts read here;
Theorem 2 instantiates an existing accountability definition.

## Theorem 3 (window condition)

Search terms: payment recall timing condition, reversal window, detection
before finality, observer order statistics.

- **Payment-channel watchtowers.** Lightning-style channels require a
  justice transaction to confirm before a timelock expires; watchtowers
  watch on behalf of offline users. Liu, Szalachowski, Sun, "Fail-safe
  Watchtowers and Short-lived Assertions for Payment Channels", AsiaCCS
  2020 (*abstract only*), and Brick (asynchronous state channels, arXiv
  1905.11360) study watchtower failure and timing. The structure "an honest
  watcher detects, reacts, and the reaction lands before an irreversibility
  deadline" is the same shape as POST-safe.
- **Byzantine fault-tolerant quickest change detection (arXiv 1306.2086)**
  raises the alarm at an order statistic of detector times so that
  corrupted detectors cannot trigger or suppress it; the (f+1)-th order
  statistic in POST-safe is the same device.
- Industry descriptions of authorization reversal, ACH reversal and wire
  recall windows give the rail windows but no formal condition.

What the paper can say: the inequality is a direct composition of known
devices (deadline-bounded reaction as in watchtowers, order statistics
against corrupted observers). The contribution is applying it per rail to
card, instant account-to-account and stablecoin payments with the void
itself and its success probability inside the condition, and measuring the
void latency. Do not claim the form of the condition as new.

## Formal analysis of agent payment protocols (arXiv 2609.00060)

Jiang, Yu, Chang, Jangid, Niu, Wang, Zhang (30 Aug 2026). Read sections
VI-B and Table II/V.

- **AP2-17, weak merchant identity binding (Sec. VI-B):** an open Payment
  Mandate with an empty merchant ID; `merchant_matches()` "falls back to
  the mutable display fields" when stable identifiers are empty, so an
  unintended merchant satisfies `allowed_payees` by name and website. The
  patched reference model requires "a nonempty, authenticated Merchant
  identifier".
- **P18:** "every actor, endpoint, or key relied on for authorization [must
  be] bound to the intended trusted principal". **P10:** runtime providers
  and payment terms must safely refine the service selected during
  discovery.

Relation: AP2-17 is PayeeBench's A2 name-clone class (a merchant matching
on display name only); B2 models mandate payee binding. The MERIDIAN
Tamarin model `checkout_ext.spthy` shows P10 and P18 hold only with the
extension. The paper should cite AP2-17 as the concrete real-world instance.

## AIP-Bench and PCAT (arXiv 2607.21824)

Dataset `anonymos-2321135/aip-bench` on Hugging Face (CC BY 4.0, revision
eaa6015, file SHA-256 8e1376bc...d99266), 14 scenarios. The GitHub
repository named in the paper (`yedidel/aip-bench-public`) was not
reachable on 7 Oct 2026. Payee-relevant scenarios (V9 wallet hijack, F-1
resolver hijack, V5 rogue marketplace injection, A-AP2-11 unauthenticated
merchant server) are replayed in `e2_aip_external`. PCAT's P2 binds a
wallet to a did:web identity, which B4 models; a lookalike domain can hold
its own did:web, which is why B4 does not stop A1/A2.

## Agentic Commerce Bench (arXiv 2609.35886)

The dataset (`withgordon/agentcommercebench`) is gated on Hugging Face and
was not used. Its fraud classes where the counterparty is who it claims to
be (overcharging) are outside MERIDIAN's object.

## F3 feasibility: can platforms issue transfer records and payout attestations?

Evidence from this repository's Stripe Connect test-mode run
(`experiments/stripe_connect.py`, table `stripe_connect`):

- The platform creates Transfer objects with an explicit `destination`
  connected account and can read them back (`GET /v1/transfers/{id}`) and
  reverse them; this is the transfer record F3 needs (G3 evidence).
- The platform lists a connected account's external bank accounts
  (`GET /v1/accounts/{id}/external_accounts`), each with a bank fingerprint,
  and observes a change of the default payout account; this is the input
  to a payout-destination attestation.

So the data exists and is available to the platform today. What does not
exist is a signed, portable form of it for a payer-side verifier: the
paper should state the signing of these records as a deployment
assumption, not as current practice.

## Still open (needs the author)

- Agency-law premise behind verifiable discharge per jurisdiction (counsel).
- FIDO Alliance agentic-payments working-group outputs (not searched).
- Full reads of the papers marked *abstract only* before citing them.
