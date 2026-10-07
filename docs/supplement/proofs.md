# Supplement: complete proofs

Statements follow the research blueprint (v2 core, 3 October 2026);
definitions are restated where a proof depends on them. Paper 1 uses
Sections 1-6, Paper 2 uses Sections 7-8. Each result is tagged with how it
is established: **proof** (here), **mechanized** (Tamarin or ProVerif,
`formal/`), **checked** (tests or toy cases).

These proofs should be checked by a reader with formal-methods or
cryptography background before submission.

## 0. Model and standing assumptions

A payment is π = (b*, p, r, c, a, m, g, t): anchored brand b*, rail payee
identifier p, rail r, currency c, amount a, merchant category m, geography
g, time t. The payment tuple is x = (r, c, a, m, g).

**Execution.** After authorization the payer's funds move along a chain of
custody transfers h₁ → h₂ → … → h_n → T, where h₁ = p and T is the
terminal account (the last account credited). Each transfer (h_j, h_{j+1},
a_j) happens at some time after authorization.

**Pre-authorization view.** View_pre(π) is everything available to the
payer-side verifier V before authorization: the RAP (edges, status proofs,
binding token β), commitments and attestations presented with it, log
state, and the payment tuple. A decision procedure is any function of
View_pre.

**Custodians.** A custodian h_j is *discretionary* if its onward
destination is chosen after authorization and is not fixed by anything in
View_pre; it is *bound* if View_pre contains a commitment signed by h_j
fixing (payment id, next hop, amount, validity) for π, bound to β.

**Assumptions (A1-A5).**
- A1 Signatures are existentially unforgeable under chosen-message attack
  (EUF-CMA).
- A2 Each issuer class performs its real check before issuing an edge
  (typed issuance, Definition 3); honest roots sign as specified.
- A3 Status lists are fresh within ρ.
- A4 The instrument released by V is scoped to exactly p, so the first
  transfer goes to h₁ = p.
- A5 Where a result needs post-authorization evidence, at least one
  observer is honest (made precise in Section 7).

The adversary (game G-PI) controls the shopping agent, can register
lookalike brands and real companies, open real platform and processor
accounts, take over some merchant dashboards (and so change a
discretionary custodian's onward choice or a payout configuration), and
corrupt up to f observers. It cannot forge honest signatures.

## 1. Lemma 1 (scope filter) — proof; checked by property tests

**Definition (scope).** σ = (R, C, A, M, G) with sets R, C, M, G and a
ceiling A ∈ ℕ ∪ {∞}. x = (r, c, a, m, g) ∈ σ iff r ∈ R, c ∈ C, a ≤ A,
m ∈ M, g ∈ G. The meet is σ ⊓ σ' = (R ∩ R', C ∩ C', min(A, A'),
M ∩ M', G ∩ G'). A path P = (e₁,…,e_k) has scope σ(P) = ⊓ᵢ σ(eᵢ).

**Lemma 1.** For every path P and tuple x: x ∈ σ(P) ⟺ ∀i: x ∈ σ(eᵢ).
Consequently DF(π) ⟺ p ∈ Reach(b*, G_t^π), where
G_t^π = {e ∈ G_t : Allowed(e) ∧ x ∈ σ(e)}.

*Proof.* For two scopes and each component: r ∈ R ∩ R' ⟺ r ∈ R ∧ r ∈ R'
(and likewise for C, M, G); a ≤ min(A, A') ⟺ a ≤ A ∧ a ≤ A'. So
x ∈ σ ⊓ σ' ⟺ x ∈ σ ∧ x ∈ σ'. The meet is associative and commutative, so
induction on k gives x ∈ ⊓ᵢ σ(eᵢ) ⟺ ∀i x ∈ σ(eᵢ).

For the corollary, unfold Definition 4: DF(π) holds iff there is a path
from b* to p whose edges are all in G_t and Allowed, and x ∈ σ(P). By the
first part the last condition is equivalent to every edge containing x.
Every condition is now a property of single edges, so DF(π) holds iff a
path from b* to p exists using only edges in G_t^π, i.e. p ∈ Reach(b*,
G_t^π). A breadth-first search decides this in O(|V| + |E|) on the
filtered graph; with a depth bound d_max it explores only paths of length
≤ d_max. ∎

**Where it fails.** If a constraint depends on the whole path (an
aggregate budget shared across edges), x ∈ σ(P) is no longer a conjunction
of per-edge conditions. Example: two edges with remaining budgets 100 each
on a shared counter of 150; each edge admits a = 100, the path does not.
This is the open problem the blueprint states.

*Checked:* `tests/test_scope_directory.py` (Hypothesis property test of
the meet; BFS against a brute-force path enumerator).

## 2. Route grammar — proof; checked

**Definition.** Read from b* to the terminal account, a valid route is a
word of R = ID⁺ (AG | SUB | CUS | ASG)* ID_term over typed edges with:
(i) SUB only after an AG or SUB edge whose delegate flag is set;
(ii) ASG sets the current principal to the assignee;
(iii) the final ID edge binds the terminal account to the current
principal; adjacent edges chain (dst(eᵢ) = src(eᵢ₊₁)).

**Proposition (one pass).** Membership of a k-edge route can be decided in
O(k) steps.

*Proof.* Ignoring identifiers, R with condition (i) is a regular language
over the finite alphabet {ID, ID_term, AG, AG^δ, SUB, SUB^δ, CUS, ASG}
(δ marking the delegate flag): condition (i) only constrains the previous
letter, which a finite automaton remembers in its state. Conditions (ii)
and (iii) compare identifiers, which a finite automaton over an unbounded
alphabet cannot do; they need one register holding the current principal,
written at the last L1 identity edge and at each ASG, and compared once
with src of the final ID edge. The chaining condition compares each edge
with its predecessor, which needs the previous edge only. A left-to-right
pass therefore does O(1) work per edge: one transition, at most one
register write and at most two identifier comparisons. Total O(k). ∎

`meridian/core/grammar.py` implements exactly this machine (states START,
IDS, CHAIN, TERM and a principal register). *Checked:* the legitimate
structures S1-S7 of F3 are accepted (`experiments/toys.py`); franchises are
not yet tested.

## 3. Theorem 1 (non-observability) and Corollary 1 — proof

**Theorem 1.** Let V be any decision procedure on View_pre. If the route
for π contains a discretionary custodian h that has issued no commitment,
then V cannot guarantee G2, G3 or G4: for every execution e in which V
allows π and the terminal account is authorized for b*, there is an
execution e′ with View_pre(e′) = View_pre(e), so V also allows π, in
which the terminal account is controlled by the adversary.

*Proof.* G2 requires, by definition, that every custodian on the route has
signed its onward destination; h has not, so G2 fails in every execution,
independent of V.

For G3 and G4, fix e. Let h = h_j be the uncommitted discretionary
custodian. Build e′ from e by changing only h's post-authorization choice:
h pays an account T′ controlled by the adversary instead of h_{j+1}, and
every later hop is removed. This change is available to the adversary,
who may take over a merchant dashboard (and so h's payout or transfer
configuration) or operate h. Because h is discretionary and uncommitted,
nothing in View_pre fixes h's onward destination, so View_pre(e′) =
View_pre(e). V is a function of View_pre, so V(e′) = V(e) = allow. In e′
the realized route departs from any authorized one at h (G3 fails) and the
credited terminal account is T′, which is not authorized for b* (G4
fails). Since e′ exists for every such e, no V that allows π can
guarantee G3 or G4. ∎

**Remarks.** (1) The argument needs no computational assumption; it is an
indistinguishability argument over pre-authorization views. (2) It does
not say post-authorization evidence is useless: G3 and G4 become
observable after the transfers, which is the subject of Theorem 3.

**Corollary 1.** If every custodian on the route has committed, G2 is
decidable from View_pre under A1.

*Proof.* G2 asks that (a) every custodian signed its onward destination,
(b) every hop is authorized for b*, and (c) the terminal account is bound
to b*'s principal or assignee. All three are predicates over objects in
View_pre: (a) is signature verification on each commitment and a check
that the committed next hops form a chain from p to a terminal account;
(b) is the route check of Section 2 plus Lemma 1 on the presented edges;
(c) is the final ID edge's signature by the account's bank and the
register comparison of Section 2. Each is computable. Under A1 a valid
signature on a commitment or ID edge was produced by the named signer
except with negligible probability, so the computed answer matches the
definition of G2. G3 and G4 refer to transfers that happen after
authorization and are not in View_pre; by Theorem 1's construction they
are not decidable from it, and Theorem 3 bounds when they can be acted on.
∎

## 4. T1 (DF soundness) — reduction; mechanized

**T1.** If PAV returns ALLOW for π at time t, then except with negligible
probability there existed at time t − ρ a chain of edges from b* to p,
each signed by its honest authorizing and accepting parties, each Allowed,
unrevoked, and with x in its scope.

*Proof.* PAV returns ALLOW only if every edge eᵢ in the RAP carries two
valid signatures (authorization ι_u by u's controller, acceptance ι_v by
v's operator), satisfies Allowed (the signer classes match the
transition), is within its validity window, has a status proof fresher
than ρ, chains to its neighbours, starts at b* and ends at p, and the meet
contains x (Lemma 1). Suppose the conclusion fails: some accepted eᵢ was
not signed by the honest party named for it, or was revoked earlier than
t − ρ. In the first case, a forger B against the signature scheme runs
the adversary, simulates every honest party except the one whose key is
under attack (guessing which of the polynomially many honest keys
appears, losing at most a polynomial factor), and outputs eᵢ with its
signature as a forgery on a message the honest party never signed. Its
success probability is the adversary's divided by the number of honest
keys, so it is negligible under A1. In the second case, the status proof
fresher than ρ contradicts A3 unless its list signature is forged, which
reduces to A1 the same way. ∎

*Mechanized:* Tamarin `df_soundness` in `formal/tamarin/meridian_v1.spthy`
with the executability lemma `executable` (both verified).

## 5. Theorem 2 (attributability) — proof; mechanized

**Setting.** V accepted π at G2 with committed route
C = (c₁, …, c_m), where c_j = Sig_{h_j}(pid, n_j, a_j, validity, β) is
custodian h_j's commitment to pay a_j to next hop n_j, h₁ = p, n_j = h_{j+1}
for j < m, and n_m = T* is the committed terminal account, bound by a
bank-signed ID edge to the current principal P of b*'s route. A *transfer
record* r = Sig_{h}(pid, src = h, dst, amount, time) is h's (or its
platform's) signed statement of a realized transfer. A *breach
certificate* is a pair (c_j, r) of a commitment and a transfer record,
both verifying under h_j's key, with the same pid, and with r.dst ≠ n_j or
r.amount < a_j.

**Theorem 2.** Suppose V accepted π at G2, and transfer records are
available for the realized hops (the T11 condition). Then, except with
negligible probability, either (a) the realized terminal account is T*,
which the route authorizes, or (b) there is a breach certificate naming a
custodian h_j on the committed route. Moreover (fairness) a breach
certificate never names a custodian who acted as committed, except with
negligible probability.

*Proof.* By A4 the first transfer reaches h₁ = p. Walk the realized hops
in order. Suppose for every j ≤ m the realized transfer out of h_j goes to
n_j with amount ≥ a_j. Then by induction on j the funds reach n_j at step
j, so at step m they reach n_m = T*, and (a) holds; T* is authorized
because V checked, at acceptance, the bank-signed ID edge binding T* to P,
and (by Corollary 1 and A1) that edge is genuine.

Otherwise let j be the first index where the realized transfer out of h_j
differs from c_j, either in destination or by a smaller amount. By the
choice of j the funds did reach h_j, so h_j made the deviating transfer
and, under the T11 condition, its transfer record r_j exists. Then
(c_j, r_j) is a breach certificate: both verify under h_j's key, share
pid, and disagree as defined. This is (b). The certificate is publicly
checkable: verifying it needs only h_j's public key and the two messages.

Fairness: if h_j acted as committed, any r with h_j's valid signature and
the same pid either matches c_j or was not produced by h_j. An honest h_j
never signs a contradicting record, so a contradicting r with a valid
signature is a forgery; a reduction as in T1 turns any adversary that
produces one into an EUF-CMA forger. ∎

**Remarks.** (1) The theorem is an instance of accountability in the
sense of Küsters, Truderung and Vogt (CCS 2010): the breach certificate is
the evidence a judge uses; fairness is their "never blame honest parties",
and (b) is completeness for the goal "funds reach T*". (2) If a deviating
custodian issues no transfer record, (b) can fail; this is the stated
boundary of T11. (3) Attributability does not prevent loss; Section 7
says when a deviation can still be undone.

*Mechanized:* Tamarin `no_false_blame` and `executable_blame`, and
`committed_route_soundness` and `commitment_authentic` (T10), in
`formal/tamarin/meridian_g2.spthy`.

## 6. Proposition 4 (split payments) — proof

**Setting.** A split plan for a payment names, for each destination k with
amount a_k, a route P_k. Some edges e carry an aggregate remaining budget
B(e) (for example a reseller's monthly cap).

**Proposition 4.** (i) Verifying a split plan takes time linear in the
total route length Σ_k |P_k| (plus the number of distinct budgeted edges).
(ii) Deciding whether a valid plan exists is strongly NP-hard, and
NP-complete.

*Proof.* (i) Check each route with the one-pass checker of Section 2 and
the per-edge checks of PAV: O(|P_k|) each. Then, in one pass over all
routes, add a_k to a counter for each budgeted edge on P_k (a hash map
keyed by edge id) and compare each counter with B(e) at the end. Total
O(Σ_k |P_k|) expected time.

(ii) Reduction from BIN PACKING, which is strongly NP-complete (Garey and
Johnson, 1979): given item sizes s₁,…,s_n, m bins and capacity C, decide
whether the items fit. Build a receiving-authority graph with one source
b*, m intermediaries I₁,…,I_m, each reachable from b* by an edge with
remaining budget C, and n destinations D₁,…,D_n, each reachable from every
intermediary by an unbudgeted edge; destination k receives amount s_k, and
every route has the form b* → I_j → D_k. A valid split plan assigns each
D_k to one I_j with the amounts through I_j summing to at most C, which is
exactly a packing of the items into m bins of capacity C. The
construction is polynomial and keeps all numbers equal to the input's, so
strong NP-hardness carries over. Membership in NP: a plan is a polynomial
certificate checked in linear time by (i). ∎

**Consequence.** The verifier should not search for splits: the party
that knows the split (platform or processor) must supply it, and V checks
it in linear time. A directory variant (V1a) that holds only standing
edges would face the search itself.

*Checked:* `meridian/core/split.py`, table `f5_split` (linear verifier
against exact search on exact-fit instances).

## 7. Theorem 3 (window condition) — proof

**Notation.** For rail r: W_r is the reversibility window (time after
authorization during which funds can still be stopped); observers
o = 1..N report a deviation with latencies δ₁,…,δ_N; δ_(i) is the i-th
smallest; δ_d is decision latency; δ_v is void (or recall) latency; s_v is
the probability that a void issued in time succeeds; ρ is the revocation
staleness bound. Probabilities are over these random quantities.

**Model assumptions.** (M1) W_r, (δ_o), δ_d, δ_v are independent of each
other and of the void's success. (M2) A corrupted observer can delay or
suppress its own report but cannot speed up an honest observer or make a
void succeed; a false report can at most cause an unnecessary void (an
availability cost, not a loss). (M3) The verifier acts on the first
report it receives and issues the void after δ_d. (M4) A diversion is
undone iff a void is issued, completes by W_r, and succeeds.

**Definition.**
POST-safe_f(r) ⟺ Pr[δ_(f+1) + δ_d + δ_v ≤ W_r] · s_v ≥ 1 − ε.
FRESH-safe(r) ⟺ ρ = 0 ∨ Pr[ρ + δ_d + δ_v ≤ W_r] · s_v ≥ 1 − ε.

**Theorem 3.** (i) Against every adversary corrupting at most f observers,
a post-authorization diversion on rail r is undone before W_r with
probability at least 1 − ε if and only if POST-safe_f(r) holds. (ii) A
payment authorized under authority revoked within the staleness window is
undone in time with probability at least 1 − ε if and only if
FRESH-safe(r) holds.

*Proof.* (i) Fix a set F of corrupted observers with |F| ≤ f. By M2 the
first report the verifier can rely on arrives at H_F = min_{o∉F} δ_o.
Among the f + 1 smallest latencies at least one belongs to an observer
outside F, so H_F ≤ δ_(f+1). An adaptive adversary that corrupts the f
fastest observers achieves H_F = δ_(f+1), and no choice of F does
better for the adversary. By M3 and M4 the diversion is undone iff
H_F + δ_d + δ_v ≤ W_r and the void succeeds; by M1 these are
independent, so

  Pr[undone | F] = Pr[H_F + δ_d + δ_v ≤ W_r] · s_v
                 ≥ Pr[δ_(f+1) + δ_d + δ_v ≤ W_r] · s_v,

with equality for the worst-case F. Hence the minimum over admissible
adversaries of Pr[undone] equals the left side of POST-safe_f, and it is
at least 1 − ε iff POST-safe_f(r) holds.

(ii) If ρ = 0 the status is checked synchronously before commit, so a
revoked authority is refused before authorization and nothing needs
undoing. Otherwise, in the worst case the revocation becomes visible to
the verifier ρ after authorization (A3 guarantees no later), and the same
argument with ρ in place of δ_(f+1) gives Pr[undone] = Pr[ρ + δ_d + δ_v ≤
W_r] · s_v in the worst case. ∎

**Corollary (T7, detection before finality).** If POST-safe_f(r) holds,
any transfer that departs from the committed route and is reported by the
observers of the corresponding level is detected and voided before W_r
with probability at least 1 − ε. *Proof:* instance of (i) with the
observers at G1 for first-hop deviations and at G3 for onward transfers.
It fails when more than f observers on the rail collude or are offline.

**Corollary (T8, impossibility on irreversible rails).** If W_r = 0 and
δ_d + δ_v > 0 almost surely, no verify-after-authorization mechanism
undoes a diversion before finality, for any f and any ε < 1. *Proof:*
Pr[δ_(f+1) + δ_d + δ_v ≤ 0] = 0, so the left side of POST-safe is 0. Only
checks completed before commit (PRE, with ρ = 0) or a construction that
makes W_r > 0 (ESCROW, where W_r becomes the escrow window) can satisfy
the condition. Recall after finality (e.g. camt.056) may recover funds but
is not undoing before finality.

**Remark (the earlier condition).** The v1 condition Pr[δ_o ≤ W_r] ≥ 1 − ε
omits δ_d, δ_v, s_v and corruption. Since δ_(f+1) ≥ δ_(1) and the added
terms are non-negative, the corrected condition is never weaker, and the
toy illustration (`f4_toy`) shows a strict gap.

**Prior art.** The structure (honest detection, then reaction, before an
irreversibility deadline, with order statistics against corrupted
detectors) is shared with payment-channel watchtowers and Byzantine
change detection; see `prior_art.md`. The paper should present Theorem 3
as an application of this structure to card, account-to-account and
stablecoin rails with the void inside the condition, not as a new form.

## 8. T9 (payee privacy) — scope

The blueprint's T9 says the verifier's view is simulatable from the ALLOW
bit and public commitments and that proofs across payments are
unlinkable. The implementation supports a narrower statement:

**T9 (as supported).** In the SNARK variant the payer learns the brand
b*, the payee identifier p, a hiding commitment to the terminal account,
and the ALLOW bit; Groth16 is perfectly zero-knowledge for an honestly
generated common reference string (its knowledge soundness rests on the
generic group model), so the proof reveals nothing further about the route:
intermediate entities, platform and processor accounts, issuers, scopes
and the terminal account stay hidden. Proofs for the same merchant are
linkable through p and the commitment; unlinkability holds only across
merchants. The BBS variant additionally reveals edge types, scopes,
issuer keys and per-edge link tags.

The Groth16 setup in this artifact uses fixed test entropy, so its
zero-knowledge and soundness guarantees do not hold for this artifact's
keys; the statement is about the scheme. *Mechanized:* the ProVerif model
`formal/proverif/private_lookup.pv` proves observational equivalence of
the k-anonymous lookup (and `private_lookup_full_hash.pv` shows the
equivalence fails when the full hash is sent).
