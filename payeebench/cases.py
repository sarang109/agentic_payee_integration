"""Benign payments and attack instances A1-A12 (plus A13 and the premise-
violation partition PV1-PV5).

Each Case records what the agent proposes (listing, payee, presented route
bundle), what the user actually meant (intended brand and words), and what
the rails would really do if the payment went through (first hop, onward
hops, terminal). Judges compare the realised terminal with ground truth.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from meridian.cba import Candidate, phash, render_logo
from meridian.core.decision import Payment
from meridian.core.edges import AG, ASG, ID, Edge
from meridian.core.keys import ETH, KeyPair
from meridian.core.ids import chain_address
from meridian.core.routes import RouteBundle
from meridian.core.scope import Scope

from .names import TECHNIQUES, lookalike
from .world import DAY, EDGE_LIFETIME, GEO_CUR, HOUR, T_EXP_END, T_EXP_START, BrandRecord, RouteTemplate, World

ATTACKS = {
    "A1": "lookalike brand surfaced",
    "A2": "fake app or merchant listing in a directory",
    "A3": "payee substituted in the checkout object",
    "A4": "feed or registry poisoning of the payment endpoint",
    "A5": "rogue sub-merchant under a real payment facilitator",
    "A6": "settlement account changed (BEC style)",
    "A7": "stale or revoked delegation reused",
    "A8": "scope abuse (rail, currency, MCC, ceiling, geography)",
    "A9": "freshly issued fake delegation from a careless issuer",
    "A10": "registry equivocation (split view)",
    "A11": "post-authorization first-hop mismatch",
    "A12": "diversion on an irreversible rail",
    "A13": "custodian deviates after committing (extra)",
}


@dataclass
class Listing:
    brand_claim: str
    display_name: str
    domain: str
    legal_name: str
    lei: str
    manifest_valid: bool = True
    curated: bool = True
    known_bad: bool = False
    looks_off: bool = False
    did_wallets: Set[str] = field(default_factory=set)
    candidate: Optional[Candidate] = None


@dataclass
class Case:
    case_id: str
    kind: str  # "benign" or attack id
    variant: str
    structure: str
    rail: str
    intended: str
    user_words: str
    listing: Listing
    payment: Payment
    bundle: Optional[RouteBundle]
    exec_first_hop: str
    exec_hops: List[Tuple[str, str, Optional[KeyPair]]]
    exec_terminal: str
    premise_violation: bool = False
    swap_after_mandate: bool = False
    receipt_visible: bool = False
    late_evidence_after: Optional[float] = None
    corrupt_observers: int = 0
    log_view: Optional[str] = None
    fork_at: Optional[int] = None
    fork_edges: List[Tuple[int, Edge]] = field(default_factory=list)
    no_gossip: bool = False
    user_confirms_stepup: bool = False
    vop_name: str = ""
    template: Optional[RouteTemplate] = None
    notes: str = ""

    @property
    def is_attack(self) -> bool:
        return self.kind != "benign"


# ------------------------------------------------------------------ helpers

def genuine_listing(br: BrandRecord, rng: random.Random) -> Listing:
    return Listing(br.brand_id, br.name, br.domain, br.entity.name, br.entity.lei, True, True, False, False,
                   set(br.did_wallets), None)


def user_words(br: BrandRecord, rng: random.Random, typo_rate: float = 0.05) -> str:
    w = br.name
    r = rng.random()
    if r < typo_rate and len(w) > 4:
        i = rng.randrange(1, len(w) - 1)
        return w[:i] + w[i + 1:]
    if r < 0.3:
        return w.lower()
    return w


def honest_exec(tpl: RouteTemplate) -> Tuple[str, List[Tuple[str, str, Optional[KeyPair]]], str]:
    hops = []
    for i, (h, key) in enumerate(tpl.custodians):
        nxt = tpl.custodians[i + 1][0] if i + 1 < len(tpl.custodians) else tpl.terminal
        hops.append((h, nxt, key))
    return tpl.payee, hops, tpl.terminal


def pick_amount(rng: random.Random, sc: Scope, cap: int = 200_000) -> int:
    hi = min(cap, sc.ceiling)
    a = int(rng.lognormvariate(8.7, 0.9))
    return max(100, min(a, hi))


def pick_rail(tpl: RouteTemplate, rng: random.Random) -> str:
    rails = [r for r in tpl.rails if tpl.scope.rails is None or r in tpl.scope.rails]
    return rng.choice(rails or list(tpl.rails))


def in_window(rng: random.Random, lo: int = T_EXP_START, hi: int = T_EXP_END) -> int:
    return rng.randrange(lo, hi)


class AttackerKit:
    """Attacker infrastructure: real companies, real platform and PSP
    accounts, own domains with valid chains."""

    def __init__(self, world: World, rng: random.Random) -> None:
        self.w = world
        self.rng = rng

    def merchant(self, name: str, domain: str, t: int, rail: str, legal: Optional[str] = None,
                 display: Optional[str] = None, geo: str = "US", category: Optional[str] = None,
                 verifier=None) -> BrandRecord:
        structure = {"a2a_instant": "S2", "stablecoin": "S12"}.get(rail, "S1")
        ent = self.w.new_entity(legal or f"{name} Trading LLC", geo, t, monitored=False)
        br = self.w.add_brand(name, structure, t, category=category, geo=geo, entity=ent, domain=domain,
                              genuine=False, monitored=False, verifier=verifier, display=display)
        self.w.build_structure(br, t)
        # attacker accounts are never legitimate for anyone else's brand
        self.w.legit.pop(br.brand_id, None)
        return br

    def entity(self, legal: str, t: int, geo: str = "US"):
        return self.w.new_entity(legal, geo, t, monitored=False)

    def psp_account(self, ent, t: int, rails=("card", "psp_token", "wallet")) -> Tuple[str, Edge, str, Edge, object]:
        w = self.w
        psp = w.psps[self.rng.choice(sorted(w.psps))]
        p = psp.new_account()
        e = psp.issue(AG, ent.lei_id, p, Scope.make(rails=set(rails)), t, t + EDGE_LIFETIME, psp.key,
                      signing_key=ent.rep)
        w.schedule_log(t, e)
        acct, te, _ = w.terminal(ent, t)
        w.schedule_payout(t, p, acct, psp.key.kid)
        return p, e, acct, te, psp


def attacker_legal_name(target: BrandRecord, rng: random.Random) -> str:
    if rng.random() < 0.5:
        return f"{target.name} {rng.choice(['Official Store', 'Payments', 'Direct', 'Retail'])} LLC"
    return f"{rng.choice(['Northwind', 'Bluefin', 'Cobalt', 'Ardent', 'Juniper'])} Commerce LLC"


def _templates_for(world: World, structures, rails=None, genuine=True):
    out = []
    for br in world.brands.values():
        if br.genuine != genuine or br.structure not in structures:
            continue
        for tpl in br.templates:
            if rails is None or any(r in rails for r in tpl.rails):
                out.append((br, tpl))
    return out


def _case(world, cid, kind, variant, br, tpl, rail, listing, pay, bundle, rng, exec_=None, **kw) -> Case:
    first, hops, term = exec_ if exec_ else honest_exec(tpl)
    return Case(cid, kind, variant, br.structure if br else "-", rail, br.brand_id if br else "",
                user_words(br, rng) if br else "", listing, pay, bundle, first, hops, term, template=tpl, **kw)


# ------------------------------------------------------------------ benign

def gen_benign(world: World, rng: random.Random, per_structure: int = 90) -> List[Case]:
    cases = []
    by_s: Dict[str, List[Tuple[BrandRecord, RouteTemplate]]] = {}
    for br in world.brands.values():
        if not br.genuine:
            continue
        for tpl in br.templates:
            by_s.setdefault(tpl.structure if br.structure != "S6" else ("S6" if "bnpl" in tpl.rails else "S1"),
                            []).append((br, tpl))
    for s, items in sorted(by_s.items()):
        for k in range(per_structure):
            br, tpl = items[k % len(items)] if k < len(items) else rng.choice(items)
            rail = pick_rail(tpl, rng)
            t0 = max(T_EXP_START, br.first_seen + 60)
            t = rng.randrange(t0, max(t0 + 1, T_EXP_END))
            if s == "S10":
                t = br.first_seen + rng.randrange(60, 8 * DAY)
            amt = pick_amount(rng, tpl.scope)
            pay = world.make_payment(tpl, rail, amt, t, rng)
            bundle = world.bundle_for(tpl, pay) if tpl.rap_edges else None
            lst = genuine_listing(br, rng)
            c = _case(world, f"benign-{s}-{k:03d}", "benign", s, br, tpl, rail, lst, pay, bundle, rng,
                      vop_name=tpl.merchant_name)
            cases.append(c)
    return cases


# ------------------------------------------------------------------ A1 / A2

def _lookalike_case(world: World, kit: AttackerKit, rng: random.Random, cid: str, kind: str, technique: str,
                    pv: bool = False) -> Optional[Case]:
    targets = [(b, t) for b, t in _templates_for(world, {"S1", "S2", "S3", "S4", "S9", "S12"})
               if b.brand_id in world.impersonated]
    br, tpl = rng.choice(targets)
    rail = pick_rail(tpl, rng)
    t = in_window(rng)
    disp, dom = lookalike(br.name, br.domain, technique, rng)
    if dom == br.domain or dom.lower() in {b.domain for b in world.brands.values()}:
        return None
    t_create = t - rng.randrange(2 * DAY, 60 * DAY)
    att = kit.merchant(disp.replace(" ", ""), dom, t_create, rail, legal=attacker_legal_name(br, rng),
                       display=disp, geo=br.geo, category=br.category)
    # the cloned site copies the genuine logo
    att.logo_hash = phash(render_logo(br.name, br.color, seed=rng.randrange(10**6), jitter=0.4))
    cand = world.registry.by_id[att.brand_id]
    cand.logo_hash = att.logo_hash
    cand.description = f"{br.name} {br.category} store"
    atpl = att.templates[0]
    pay = world.make_payment(atpl, rail if rail in atpl.rails else atpl.rails[0], pick_amount(rng, atpl.scope), t, rng)
    bundle = world.bundle_for(atpl, pay)
    lst = Listing(att.brand_id, disp, dom, att.entity.name, att.entity.lei, manifest_valid=rng.random() < 0.6,
                  curated=rng.random() < 0.5, known_bad=rng.random() < 0.1, looks_off=True,
                  did_wallets=set(att.did_wallets), candidate=cand)
    c = Case(cid, kind, technique, br.structure, pay.rail, br.brand_id, user_words(br, rng, 0.0), lst, pay, bundle,
             *honest_exec(atpl), template=atpl, vop_name=att.entity.name, premise_violation=pv,
             user_confirms_stepup=pv)
    return c


def gen_A1(world, kit, rng, n) -> List[Case]:
    out = []
    techs = [t for t in TECHNIQUES if t != "name-clone"]
    i = 0
    while len(out) < n:
        c = _lookalike_case(world, kit, rng, f"A1-{len(out):03d}", "A1", techs[i % len(techs)])
        i += 1
        if c:
            out.append(c)
    return out


def gen_A2(world, kit, rng, n) -> List[Case]:
    out = []
    while len(out) < n:
        c = _lookalike_case(world, kit, rng, f"A2-{len(out):03d}", "A2", "name-clone")
        if c:
            c.listing.curated = rng.random() < 0.6
            out.append(c)
    return out


# ------------------------------------------------------------------ A3 / A4

def _swap_case(world, kit, rng, cid, kind, variant, targets=None) -> Case:
    br, tpl = rng.choice(targets or _templates_for(world, {"S1", "S2", "S3", "S4", "S9", "S12", "S13"}))
    rail = pick_rail(tpl, rng)
    t = in_window(rng)
    att = kit.merchant(f"Px{rng.randrange(10**6)}", f"px{rng.randrange(10**8)}.com", t - rng.randrange(DAY, 30 * DAY),
                       rail, legal=attacker_legal_name(br, rng), geo=br.geo, category=br.category)
    atpl = att.templates[0]
    orig = world.make_payment(tpl, rail, pick_amount(rng, tpl.scope), t, rng)
    pay = Payment(orig.payment_id, atpl.payee, orig.rail, "USDC" if rail == "stablecoin" else orig.currency,
                  orig.amount, orig.mcc, orig.geo, t, orig.cart_digest, orig.nonce)
    if variant == "swap-keep-rap":
        bundle = world.bundle_for(tpl, orig)
    elif variant == "swap-own-rap":
        bundle = world.bundle_for(atpl, pay)
    else:
        bundle = None
    lst = genuine_listing(br, rng)
    return Case(cid, kind, variant, br.structure, rail, br.brand_id, user_words(br, rng), lst, pay, bundle,
                *honest_exec(atpl), template=tpl, swap_after_mandate=(kind == "A3" and rng.random() < 0.5),
                vop_name=att.entity.name)


def gen_A3(world, kit, rng, n):
    vs = ["swap-keep-rap", "swap-own-rap", "swap-no-rap"]
    return [_swap_case(world, kit, rng, f"A3-{i:03d}", "A3", vs[i % 3]) for i in range(n)]


def gen_A4(world, kit, rng, n):
    vs = ["feed-own-rap", "feed-no-rap"]
    out = []
    for i in range(n):
        c = _swap_case(world, kit, rng, f"A4-{i:03d}", "A4", "swap-own-rap" if i % 2 == 0 else "swap-no-rap")
        c.variant = vs[i % 2]
        out.append(c)
    return out


# ------------------------------------------------------------------ A5

def gen_A5(world, kit, rng, n):
    out = []
    targets = [(br, tpl) for br, tpl in _templates_for(world, {"S1", "S3", "S4", "S9"}) if "card" in tpl.rails]
    for i in range(n):
        br, tpl = rng.choice(targets)
        t = in_window(rng)
        pf = world.payfacs[rng.choice(sorted(world.payfacs))]
        ent = kit.entity(attacker_legal_name(br, rng), t - rng.randrange(DAY, 30 * DAY), br.geo)
        sub = pf.new_account("sub")
        e = pf.issue(AG, ent.lei_id, sub, Scope.make(rails={"card"}), ent.registered_at, ent.registered_at + EDGE_LIFETIME,
                     pf.key, signing_key=ent.rep)
        world.schedule_log(ent.registered_at, e)
        acct, te, _ = world.terminal(ent, ent.registered_at)
        world.schedule_payout(ent.registered_at, sub, acct, pf.key.kid)
        atpl = RouteTemplate(world.next_id("rt"), "", "S4", ("card",), [e], sub, pf.key, [], [(sub, pf.key)], acct,
                             te, Scope.make(rails={"card"}), ent.lei, ent.name, pf.name)
        pay = world.make_payment(tpl, "card", pick_amount(rng, tpl.scope), t, rng, payee=sub)
        variant = "no-rap" if i % 2 == 0 else "entity-rap"
        bundle = None if variant == "no-rap" else world.bundle_for(atpl, pay)
        lst = Listing(br.brand_id, br.name, f"{pf.name}.example", ent.name, ent.lei, manifest_valid=True,
                      curated=rng.random() < 0.7, known_bad=rng.random() < 0.1, looks_off=False)
        out.append(Case(f"A5-{i:03d}", "A5", variant, br.structure, "card", br.brand_id, user_words(br, rng), lst,
                        pay, bundle, *honest_exec(atpl), template=atpl, vop_name=ent.name))
    return out


# ------------------------------------------------------------------ A6

def gen_A6(world, kit, rng, n):
    out = []
    card = [(b, t) for b, t in _templates_for(world, {"S1", "S4", "S9"}) if "card" in t.rails]
    a2a = _templates_for(world, {"S2"})
    coin = _templates_for(world, {"S12"})
    for i in range(n):
        kind = ["card", "a2a", "coin"][i % 3]
        t = in_window(rng)
        mule = kit.entity(rng.choice(["Mule Holdings LLC", "Quick Settle Ltd", "Harbor Supply LLC"]), t - 40 * DAY)
        if kind == "card":
            br, tpl = rng.choice(card)
            t_change = t - rng.randrange(HOUR, 2 * DAY)
            acct, te, bank = world.terminal(mule, t - 40 * DAY)
            # dashboard takeover: the PSP now honestly attests the new payout
            world.schedule_payout(t_change, tpl.payee, acct, tpl.custodians[-1][1].kid)
            pay = world.make_payment(tpl, "card", pick_amount(rng, tpl.scope), t, rng)
            bundle = world.bundle_for(tpl, pay, payout_override=acct, terminal_override=te)
            hops = [(tpl.payee, acct, tpl.custodians[-1][1])]
            out.append(Case(f"A6-{i:03d}", "A6", "card-payout-change", br.structure, "card", br.brand_id,
                            user_words(br, rng), genuine_listing(br, rng), pay, bundle, tpl.payee, hops, acct,
                            template=tpl, vop_name=tpl.merchant_name))
        elif kind == "a2a":
            br, tpl = rng.choice(a2a)
            acct, te, bank = world.terminal(mule, t - 40 * DAY)
            orig = world.make_payment(tpl, "a2a_instant", pick_amount(rng, tpl.scope), t, rng)
            pay = Payment(orig.payment_id, acct, "a2a_instant", orig.currency, orig.amount, orig.mcc, orig.geo, t,
                          orig.cart_digest, orig.nonce)
            bundle = world.bundle_for(tpl, orig) if i % 2 else None
            out.append(Case(f"A6-{i:03d}", "A6", "a2a-invoice-account", br.structure, "a2a_instant", br.brand_id,
                            user_words(br, rng), genuine_listing(br, rng), pay, bundle, acct, [], acct,
                            template=tpl, vop_name=tpl.merchant_name))
        else:
            br, tpl = rng.choice(coin)
            wkey = KeyPair(ETH)
            addr = chain_address("eip155:84532", wkey.public.address)
            world.owner[addr] = mule.lei
            orig = world.make_payment(tpl, "stablecoin", pick_amount(rng, tpl.scope), t, rng)
            pay = Payment(orig.payment_id, addr, "stablecoin", "USDC", orig.amount, orig.mcc, orig.geo, t,
                          orig.cart_digest, orig.nonce)
            lst = genuine_listing(br, rng)
            if rng.random() < 0.3:  # did:web document also rewritten
                lst.did_wallets = {addr}
            bundle = world.bundle_for(tpl, orig) if i % 2 else None
            out.append(Case(f"A6-{i:03d}", "A6", "coin-payto-change", br.structure, "stablecoin", br.brand_id,
                            user_words(br, rng), lst, pay, bundle, addr, [], addr, template=tpl,
                            vop_name=tpl.merchant_name))
    return out


# ------------------------------------------------------------------ A7 / A8

def _reseller(world: World, br: BrandRecord, t0: int, rng: random.Random, sc: Scope, name: str):
    """A fresh delegation from br to a reseller entity, created at t0."""
    rent = world.new_entity(name, sorted(sc.geos)[0] if sc.geos else br.geo, t0)
    ei = world.entity_issuers[br.entity.lei]
    e1 = ei.issue(ASG, br.entity.lei_id, rent.lei_id, sc, t0, t0 + EDGE_LIFETIME, rent.rep)
    world.schedule_log(t0, e1)
    psp = world.psps[rng.choice(sorted(world.psps))]
    p = psp.new_account()
    e2 = psp.issue(AG, rent.lei_id, p, sc, t0, t0 + EDGE_LIFETIME, psp.key, signing_key=rent.rep)
    world.schedule_log(t0, e2)
    acct, te, _ = world.terminal(rent, t0)
    world.schedule_payout(t0, p, acct, psp.key.kid)
    world.watch(rent, {p}, {acct})
    tpl = RouteTemplate(world.next_id("rt"), br.brand_id, "S5", ("card", "psp_token"),
                        [world.brand_edge(br), e1, e2], p, psp.key, [], [(p, psp.key)], acct, te,
                        sc.meet(world.brand_edge(br).scope), rent.lei, rent.name, psp.name)
    return tpl, e1, ei


def gen_A7(world, kit, rng, n, rho: int = 300, pv: bool = False):
    out = []
    targets = [b for b in world.brands.values() if b.genuine and b.structure in ("S1", "S3", "S4", "S9")]
    for i in range(n):
        br = rng.choice(targets)
        t = in_window(rng)
        sc = Scope.make(rails={"card", "psp_token"}, currencies={br.currency}, mccs={br.mcc}, geos={br.geo},
                        ceiling=500_000)
        tpl, e1, ei = _reseller(world, br, t - 200 * DAY, rng, sc, f"{br.name} Former Reseller Ltd")
        t_rev = t - rng.randrange(2 * rho, 20 * DAY)
        variant = ["stale-snapshot", "fresh-snapshot"][i % 2]
        if pv:
            variant = "revocation-published-late"
            # truth: revoked at t_rev; the issuer publishes only after payment
            ei.status_list.revoke(e1.status.index, t + HOUR)
        else:
            ei.status_list.revoke(e1.status.index, t_rev)
        world.legit.setdefault(br.brand_id, [])  # the former reseller is not legitimate any more
        pay = world.make_payment(tpl, "card", pick_amount(rng, tpl.scope), t, rng)
        snap_t = t_rev - 60 if variant == "stale-snapshot" else t
        bundle = world.bundle_for(tpl, pay, snap_t=snap_t)
        lst = genuine_listing(br, rng)
        out.append(Case(f"{'PV3' if pv else 'A7'}-{i:03d}", "PV3" if pv else "A7", variant, br.structure, "card",
                        br.brand_id, user_words(br, rng), lst, pay, bundle, *honest_exec(tpl), template=tpl,
                        premise_violation=pv, vop_name=tpl.merchant_name))
    return out


def gen_A8(world, kit, rng, n):
    out = []
    targets = [b for b in world.brands.values() if b.genuine and b.structure in ("S1", "S3", "S4", "S9", "S12")]
    variants = ["geo", "ceiling", "currency", "mcc", "rail"]
    for i in range(n):
        br = rng.choice(targets)
        t = in_window(rng)
        sc = Scope.make(rails={"card"}, currencies={br.currency}, mccs={br.mcc}, geos={br.geo}, ceiling=300_000)
        tpl, _, _ = _reseller(world, br, t - 100 * DAY, rng, sc, f"{br.name} Licensed Reseller Ltd")
        world.legit.setdefault(br.brand_id, []).append((tpl.scope, tpl.terminal))
        v = variants[i % len(variants)]
        geo = "GB" if br.geo != "GB" else "DE"
        kw = {}
        amt = pick_amount(rng, tpl.scope)
        rail = "card"
        if v == "geo":
            kw["geo"] = geo
        elif v == "ceiling":
            amt = 300_000 + rng.randrange(1000, 500_000)
        elif v == "currency":
            kw["currency"] = "EUR" if br.currency != "EUR" else "GBP"
        elif v == "mcc":
            kw["mcc"] = "5732" if br.mcc != "5732" else "5942"
        else:
            rail = "psp_token"
        pay = world.make_payment(tpl, rail, amt, t, rng, **kw)
        bundle = world.bundle_for(tpl, pay)
        out.append(Case(f"A8-{i:03d}", "A8", v, br.structure, rail, br.brand_id, user_words(br, rng),
                        genuine_listing(br, rng), pay, bundle, *honest_exec(tpl), template=tpl,
                        vop_name=tpl.merchant_name))
    return out


# ------------------------------------------------------------------ A9 / A10

def _fake_binding(world, kit, rng, br, t_fake, log: bool = True):
    ent = kit.entity(attacker_legal_name(br, rng), t_fake - 30 * DAY, br.geo)
    dv = world.dv_careless
    val = dv.challenge(br.domain, ent.rep)  # never placed in DNS; the careless verifier does not look
    fake = dv.bind(br.domain, ent, world.dns, t_fake, t_fake + EDGE_LIFETIME)
    if log:
        world.schedule_log(t_fake, fake)
    p, e, acct, te, psp = kit.psp_account(ent, t_fake)
    tpl = RouteTemplate(world.next_id("rt"), br.brand_id, "S1", ("card", "psp_token"), [fake, e], p, psp.key, [],
                        [(p, psp.key)], acct, te, Scope.make(rails={"card", "psp_token"}), ent.lei, ent.name, psp.name)
    return tpl, fake, ent


def gen_A9(world, kit, rng, n, pv: bool = False, strategy: str = "rush"):
    out = []
    targets = [b for b in world.brands.values() if b.genuine and b.structure in ("S1", "S3", "S4", "S9", "S2")]
    for i in range(n):
        br = rng.choice(targets)
        t_fake = in_window(rng, T_EXP_START - 20 * DAY, T_EXP_END - 20 * DAY)
        tpl, fake, ent = _fake_binding(world, kit, rng, br, t_fake)
        if pv:
            # premise violation: the brand's monitor is offline during probation
            # and the attacker waits it out
            d = world.delta + rng.randrange(HOUR, 3 * DAY)
            world.monitors[br.entity.lei].ignore_refs.add(fake.eid)
        elif strategy == "patient":
            d = world.delta + rng.randrange(HOUR, 3 * HOUR)  # waits out probation
        else:
            d = int(rng.lognormvariate(10.3, 1.2))  # attacker cashes out fast (median ~8h)
        t = t_fake + max(600, d)
        pay = world.make_payment(tpl, "card", pick_amount(rng, Scope.make(ceiling=200_000)), t, rng,
                                 currency=br.currency, mcc=br.mcc, geo=br.geo)
        bundle = world.bundle_for(tpl, pay)
        lst = Listing(br.brand_id, br.name, br.domain, ent.name, ent.lei, manifest_valid=rng.random() < 0.5,
                      curated=True, known_bad=rng.random() < 0.05, looks_off=False)
        out.append(Case(f"{'PV1' if pv else 'A9'}-{i:03d}", "PV1" if pv else "A9",
                        "careless-domain-verifier" if not pv else "monitor-misses-claim",
                        br.structure, "card", br.brand_id, user_words(br, rng), lst, pay, bundle,
                        *honest_exec(tpl), template=tpl, premise_violation=pv, vop_name=ent.name,
                        notes=f"use after {d}s"))
    return out


def gen_A10(world, kit, rng, n, pv: bool = False):
    out = []
    targets = [b for b in world.brands.values() if b.genuine and b.structure in ("S1", "S3", "S4", "S9")]
    for i in range(n):
        br = rng.choice(targets)
        t_fork = in_window(rng, T_EXP_START - 20 * DAY, T_EXP_END - 20 * DAY)
        tpl, fake, ent = _fake_binding(world, kit, rng, br, t_fork, log=False)
        t = t_fork + world.delta + rng.randrange(HOUR, 2 * DAY)
        pay = world.make_payment(tpl, "card", pick_amount(rng, Scope.make(ceiling=200_000)), t, rng,
                                 currency=br.currency, mcc=br.mcc, geo=br.geo)
        bundle = world.bundle_for(tpl, pay)
        lst = Listing(br.brand_id, br.name, br.domain, ent.name, ent.lei, manifest_valid=rng.random() < 0.5)
        kind = "PV4" if pv else "A10"
        out.append(Case(f"{kind}-{i:03d}", kind, "split-view", br.structure, "card", br.brand_id,
                        user_words(br, rng), lst, pay, bundle, *honest_exec(tpl), template=tpl,
                        log_view=f"fork-{kind}-{i}", fork_at=t_fork, fork_edges=[(t_fork, fake)], no_gossip=pv,
                        premise_violation=pv, vop_name=ent.name))
    return out


# ------------------------------------------------------------------ A11 / A13

def gen_A11(world, kit, rng, n, pv: bool = False, targets=None, prefix: str = ""):
    out = []
    targets = targets or [(b, t) for b, t in _templates_for(world, {"S1", "S3", "S4", "S9", "S7"}) if "card" in t.rails]
    for i in range(n):
        br, tpl = rng.choice(targets)
        t = in_window(rng)
        ent = kit.entity(rng.choice(["Laundry Retail LLC", "Mirror Goods Ltd", "Proxy Trading LLC"]), t - 60 * DAY)
        p2, _, acct2, _, psp2 = kit.psp_account(ent, t - 60 * DAY)
        rail = "card" if "card" in tpl.rails else tpl.rails[0]
        pay = world.make_payment(tpl, rail, pick_amount(rng, tpl.scope), t, rng)
        bundle = world.bundle_for(tpl, pay)
        variant = ["transaction-laundering", "acquirer-level-swap"][i % 2]
        kind = "PV2" if pv else "A11"
        out.append(Case(f"{prefix}{kind}-{i:03d}", kind, variant, br.structure, rail, br.brand_id, user_words(br, rng),
                        genuine_listing(br, rng), pay, bundle, p2, [(p2, acct2, psp2.key)], acct2, template=tpl,
                        receipt_visible=(variant == "transaction-laundering"),
                        corrupt_observers=99 if pv else 0, premise_violation=pv, vop_name=tpl.merchant_name))
    return out


def gen_A13(world, kit, rng, n, targets=None, prefix: str = ""):
    out = []
    targets = targets or _templates_for(world, {"S3", "S7"})
    for i in range(n):
        br, tpl = rng.choice(targets)
        t = in_window(rng)
        ent = kit.entity("Insider Payouts LLC", t - 60 * DAY)
        acct, _, _ = world.terminal(ent, t - 60 * DAY)
        rail = pick_rail(tpl, rng)
        pay = world.make_payment(tpl, rail, pick_amount(rng, tpl.scope), t, rng)
        bundle = world.bundle_for(tpl, pay)
        main, key = tpl.custodians[0]
        hops = [(main, acct, key)]
        out.append(Case(f"{prefix}A13-{i:03d}", "A13", "custodian-deviates", br.structure, rail, br.brand_id,
                        user_words(br, rng), genuine_listing(br, rng), pay, bundle, tpl.payee, hops, acct,
                        template=tpl, vop_name=tpl.merchant_name))
    return out


# ------------------------------------------------------------------ BNPL supplement

def gen_bnpl(world, kit, rng, n) -> List[Case]:
    """Attacks on the BNPL route (S6: brand -> lender by assignment -> lender's
    PSP account). The pre-registered bench has none, so the BNPL row of the
    per-rail comparison has no attack data; this set fills it. It is built on
    its own world so the pre-registered bench is unchanged. The lender payout
    account is shared by every S6 brand, so a lender payout change (A6) would
    also redirect the benign payments and is left out."""
    targets = [(b, t) for b, t in _templates_for(world, {"S6"}) if "bnpl" in t.rails]
    out: List[Case] = []
    k = n // 4
    for i in range(k):
        c = _swap_case(world, kit, rng, f"BNPL-A3-{i:03d}", "A3", ["swap-keep-rap", "swap-own-rap", "swap-no-rap"][i % 3],
                       targets=targets)
        out.append(c)
    for i in range(k):
        c = _swap_case(world, kit, rng, f"BNPL-A4-{i:03d}", "A4", "swap-own-rap" if i % 2 == 0 else "swap-no-rap",
                       targets=targets)
        c.variant = ["feed-own-rap", "feed-no-rap"][i % 2]
        out.append(c)
    out += gen_A11(world, kit, rng, k, targets=targets, prefix="BNPL-")
    out += gen_A13(world, kit, rng, n - 3 * k, targets=targets, prefix="BNPL-")
    for c in out:
        c.variant = f"bnpl:{c.variant}"
    return out


# ------------------------------------------------------------------ external specifications

AIP_SCENARIOS = {
    "AIP:V9": "rogue federation server returns the attacker's wallet as payee (CoralOS V9)",
    "AIP:F-1": "agent-address resolver hijacked; checkout served by the attacker's endpoint (Fetch.ai F-1)",
    "AIP:V5": "rogue marketplace listing injects a payee redirect into the agent (CoralOS V5)",
    "AIP:A-AP2-11": "unauthenticated merchant MCP server lets the attacker rewrite checkout after the mandate "
                    "(AP2 A-AP2-11)",
}


def gen_aip_external(world, kit, rng, n_per: int) -> List[Case]:
    """Payee-diversion scenarios specified by AIP-Bench (Louck, arXiv
    2607.21824; dataset anonymos-2321135/aip-bench, CC BY 4.0), replayed as
    payments. The scenario fixes what the attacker controls; the instance
    (brand, rail, attacker infrastructure) comes from the generator. Each
    scenario is run with and without an attacker-held RAP for its own entity."""
    coin = _templates_for(world, {"S12"})
    other = _templates_for(world, {"S1", "S2", "S3", "S4", "S9", "S13"})
    out: List[Case] = []
    for sid in AIP_SCENARIOS:
        for i in range(n_per):
            variant = "swap-own-rap" if i % 2 == 0 else "swap-no-rap"
            kind = "A4" if sid == "AIP:F-1" else "A3"
            c = _swap_case(world, kit, rng, f"{sid}-{i:03d}", kind, variant,
                           targets=coin if sid == "AIP:V9" else other)
            c.swap_after_mandate = sid == "AIP:A-AP2-11"
            c.variant = f"{sid}:{variant}"
            out.append(c)
    return out


# ------------------------------------------------------------------ A12

def gen_A12(world, kit, rng, n, rho: int = 300):
    """Irreversible rails. 'stale-authority': the account was reported
    compromised and its binding revoked within the verifier's staleness
    window. 'late-revocation': the account is already compromised but the
    revocation lands only after authorization."""
    out = []
    for i in range(n):
        rail = ["a2a_instant", "stablecoin"][i % 2]
        variant = ["stale-authority", "late-revocation"][(i // 2) % 2]
        br = rng.choice([b for b in world.brands.values() if b.genuine and b.structure == ("S2" if rail == "a2a_instant" else "S12")])
        t = in_window(rng)
        t0 = t - 120 * DAY
        ent = br.entity
        ei = world.entity_issuers[ent.lei]
        if rail == "a2a_instant":
            acct, te, bank = world.terminal(ent, t0)
            issuer = bank
            payee = acct
            beta_key = ent.rep
            edge = te
        else:
            wkey = KeyPair(ETH)
            payee = chain_address("eip155:84532", wkey.public.address)
            world.trust.add_wallet(payee, wkey.public)
            world.owner[payee] = ent.lei
            sc = Scope.make(rails={"stablecoin"}, currencies={"USDC"}, mccs={br.mcc}, ceiling=2_000_000)
            edge = ei.issue(ID, ent.lei_id, payee, sc, t0, t0 + EDGE_LIFETIME, wkey)
            world.schedule_log(t0, edge)
            issuer = ei
            beta_key = wkey
        tpl = RouteTemplate(world.next_id("rt"), br.brand_id, br.structure, (rail,), [world.brand_edge(br), edge],
                            payee, beta_key, [], [], payee, edge, edge.scope.meet(world.brand_edge(br).scope), ent.lei,
                            ent.name)
        late = None
        if variant == "stale-authority":
            t_rev = t - rng.randrange(10, rho)
            issuer.status_list.revoke(edge.status.index, t_rev)
            snap_t = t_rev - 1
        else:
            t_rev = t + rng.randrange(30, 400)
            issuer.status_list.revoke(edge.status.index, t_rev)
            snap_t = t
            late = float(t_rev - t + rng.randrange(1, 20))  # status propagation to the verifier
        pay = world.make_payment(tpl, rail, pick_amount(rng, tpl.scope), t, rng)
        bundle = world.bundle_for(tpl, pay, snap_t=snap_t)
        out.append(Case(f"A12-{i:03d}", "A12", f"{rail}:{variant}", br.structure, rail, br.brand_id,
                        user_words(br, rng), genuine_listing(br, rng), pay, bundle, payee, [], payee,
                        template=tpl, late_evidence_after=late, vop_name=ent.name,
                        notes="terminal account compromised (attacker-controlled)"))
        world.compromised.add(payee)
    return out


# ------------------------------------------------------------------ PV5

def gen_PV5(world, kit, rng, n):
    out = []
    techs = ["homoglyph", "affix", "name-clone", "tld-swap"]
    while len(out) < n:
        c = _lookalike_case(world, kit, rng, f"PV5-{len(out):03d}", "PV5", techs[len(out) % 4], pv=True)
        if c:
            out.append(c)
    return out


GENERATORS: Dict[str, Callable] = {
    "A1": gen_A1, "A2": gen_A2, "A3": gen_A3, "A4": gen_A4, "A5": gen_A5, "A6": gen_A6, "A7": gen_A7,
    "A8": gen_A8, "A9": gen_A9, "A10": gen_A10, "A11": gen_A11, "A12": gen_A12, "A13": gen_A13,
}
PV_GENERATORS: Dict[str, Callable] = {
    "PV1": lambda w, k, r, n: gen_A9(w, k, r, n, pv=True),
    "PV2": lambda w, k, r, n: gen_A11(w, k, r, n, pv=True),
    "PV3": lambda w, k, r, n: gen_A7(w, k, r, n, pv=True),
    "PV4": lambda w, k, r, n: gen_A10(w, k, r, n, pv=True),
    "PV5": gen_PV5,
}
PV_DESCRIPTIONS = {
    "PV1": "compromised (careless) root issues a false brand edge and the brand monitor is offline during probation",
    "PV2": "all V3 observers on the rail collude",
    "PV3": "revocation published later than the staleness bound rho",
    "PV4": "split view with every gossip peer colluding (no honest gossip)",
    "PV5": "user explicitly confirms a lookalike at step-up",
}
