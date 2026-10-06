"""PayeeBench ecosystem generator.

Builds a merchant ecosystem with real signed credentials: brands, legal
entities, platforms and marketplaces, PSPs, payment facilitators, merchants
of record, BNPL lenders, franchises, banks and wallets. Every legitimate way
to pay a brand is a RouteTemplate; ground truth (who really owns each
terminal account and which delegations the brand really granted) is kept
separately from the credentials so judges never trust what the verifier
sees.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from meridian.cba import Candidate, Registry, phash, render_logo
from meridian.core.decision import Payment
from meridian.core.edges import AG, ASG, CUS, ID, SUB, Edge
from meridian.core.ids import chain_address, make_lei
from meridian.core.keys import ETH, KeyPair
from meridian.core.pav import RAP, BindingToken
from meridian.core.policy import ENTITY_REP, TrustStore
from meridian.core.routes import PAYOUT, REMIT, Commitment, RouteBundle
from meridian.core.scope import Scope
from meridian.core.status import StatusRegistry
from meridian.issuers import QVI, Bank, DomainVerifier, EscrowOperator, LegalEntity, Platform, PSPOperator, make_entity
from meridian.issuers.base import Issuer, Operator
from meridian.log import BrandMonitor, GossipPool, MerchantTransparencyLog, lognormal_seconds

from .names import unique_brands

DAY = 86400
HOUR = 3600
T_EXP_START = 300 * DAY
T_EXP_END = 330 * DAY
EDGE_LIFETIME = 3 * 365 * DAY

STRUCTURES = {
    "S1": "direct card merchant",
    "S2": "direct account-to-account",
    "S3": "brand store on a marketplace",
    "S4": "payment facilitator sub-merchant",
    "S5": "merchant of record / reseller",
    "S6": "buy-now-pay-later lender",
    "S7": "agent platform as merchant of record",
    "S8": "franchise (geography-scoped)",
    "S9": "multi-brand group",
    "S10": "newly onboarded merchant",
    "S11": "small merchant without credentials",
    "S12": "direct stablecoin merchant",
    "S13": "escrow custody (held funds)",
}

STRUCTURE_RAILS = {
    "S1": ("card", "psp_token", "wallet"), "S2": ("a2a_instant",), "S3": ("card", "psp_token"), "S4": ("card",),
    "S5": ("card", "psp_token"), "S6": ("bnpl",), "S7": ("psp_token", "card"), "S8": ("card",), "S9": ("card",),
    "S10": ("card",), "S11": ("card", "a2a_instant"), "S12": ("stablecoin",), "S13": ("card",),
}

MCC_BY_CATEGORY = {"shoes": "5661", "apparel": "5651", "electronics": "5732", "books": "5942", "toys": "5945",
                   "grocery": "5411", "software": "5734", "home": "5719", "sports": "5941", "beauty": "5977"}
GEO_CUR = {"US": "USD", "GB": "GBP", "DE": "EUR", "FR": "EUR", "IN": "INR", "NL": "EUR", "ES": "EUR"}
BANK_FOR_GEO = {"US": "bnkus1", "GB": "bnkuk1", "DE": "bnkeu1", "FR": "bnkeu1", "NL": "bnkeu1", "ES": "bnkeu1",
                "IN": "bnkin1"}


class EntityIssuer(Issuer):
    """An entity's own status list, hosted under its representative key, for
    edges the entity authorises itself (assignments, wallet bindings)."""

    def __init__(self, entity: LegalEntity, status_registry: StatusRegistry):
        super().__init__(entity.lei, ENTITY_REP, set(), status_registry, key=entity.rep)


@dataclass
class RouteTemplate:
    tid: str
    brand: str
    structure: str
    rails: Tuple[str, ...]
    rap_edges: List[Edge]
    payee: str
    beta_key: KeyPair
    onward: List[Edge]
    custodians: List[Tuple[str, KeyPair]]
    terminal: str
    terminal_edge: Optional[Edge]
    scope: Scope
    owner_lei: str
    merchant_name: str
    payee_operator: str = ""

    def all_edges(self) -> List[Edge]:
        out = list(self.rap_edges) + list(self.onward)
        if self.terminal_edge is not None and self.terminal_edge not in out:
            out.append(self.terminal_edge)
        return out


@dataclass
class BrandRecord:
    brand_id: str
    name: str
    domain: str
    entity: LegalEntity
    structure: str
    category: str
    geo: str
    currency: str
    templates: List[RouteTemplate] = field(default_factory=list)
    logo_hash: int = 0
    color: Tuple[int, int, int] = (0, 0, 0)
    did_wallets: Set[str] = field(default_factory=set)
    first_seen: int = 0
    genuine: bool = True

    @property
    def mcc(self) -> str:
        return MCC_BY_CATEGORY[self.category]


class World:
    def __init__(self, seed: int = 7, n_brands: int = 130, delta: int = 3 * DAY,
                 monitor_median_s: float = 6 * HOUR, monitor_sigma: float = 1.0) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.delta = delta
        self.sr = StatusRegistry()
        self.trust = TrustStore()
        self.log = MerchantTransparencyLog("mtl-1")
        self.gossip = GossipPool()
        self.dns: Dict[str, List[str]] = {}
        self.brands: Dict[str, BrandRecord] = {}
        self.entities: Dict[str, LegalEntity] = {}
        self.entity_issuers: Dict[str, EntityIssuer] = {}
        self.monitors: Dict[str, BrandMonitor] = {}
        self.owner: Dict[str, str] = {}  # terminal account -> owning LEI (truth)
        self.compromised: Set[str] = set()  # accounts under attacker control (truth)
        self.impersonated: Set[str] = set()
        self.legit: Dict[str, List[Tuple[Scope, str]]] = {}  # brand -> (scope, terminal) granted for real
        self.log_events: List[Tuple[int, str, object]] = []
        self.registry = Registry()
        self.monitor_reaction = lognormal_seconds(monitor_median_s, monitor_sigma)
        self._brand_edges: Dict[str, Edge] = {}
        self._mon_rng = random.Random(seed + 1)
        self._ids = 0
        self._roots()
        self.n_brands = n_brands

    # ------------------------------------------------------------ roots
    def _roots(self) -> None:
        sr = self.sr
        self.dv = DomainVerifier("dv-honest", sr)
        self.dv_careless = DomainVerifier("dv-careless", sr, careless=True)
        self.qvi = QVI("qvi-1", sr)
        self.psps = {n: PSPOperator(n, sr) for n in ("pspone", "psptwo")}
        self.marketplaces = {n: Platform(n, sr) for n in ("mktalpha", "mktbeta")}
        self.payfacs = {n: Platform(n, sr) for n in ("payfacone", "payfactwo")}
        self.agentplat = Platform("agentplat", sr)
        self.escrow = EscrowOperator("escrowone", sr)
        self.banks = {n: Bank(n, sr) for n in ("bnkus1", "bnkuk1", "bnkeu1", "bnkin1")}
        for i in [self.dv, self.dv_careless, self.qvi, self.agentplat, self.escrow, *self.psps.values(),
                  *self.marketplaces.values(), *self.payfacs.values(), *self.banks.values()]:
            i.register(self.trust)
        self.log.watchers.append(self._on_log)

    def _on_log(self, entry, view) -> None:
        for m in self.monitors.values():
            m.observe(entry, view)

    def operators(self) -> Dict[str, Operator]:
        out = {}
        for d in (self.psps, self.marketplaces, self.payfacs, self.banks):
            out.update(d)
        out["agentplat"] = self.agentplat
        out["escrowone"] = self.escrow
        return out

    # ------------------------------------------------------------ helpers
    def next_id(self, prefix: str) -> str:
        self._ids += 1
        return f"{prefix}{self._ids:05d}"

    def new_entity(self, name: str, jurisdiction: str, t: int, monitored: bool = True,
                   domains: Set[str] = frozenset()) -> LegalEntity:
        lei = make_lei(f"{self.seed}|{name}|{self._ids}")
        self._ids += 1
        ent = make_entity(name, lei, jurisdiction, t)
        self.entities[lei] = ent
        self.trust.add_role_credential(self.qvi.role_credential(ent, t + EDGE_LIFETIME), now=t)
        self.entity_issuers[lei] = EntityIssuer(ent, self.sr)
        if monitored:
            self.monitors[lei] = BrandMonitor(lei, ent.rep.kid, set(domains), set(), set(), self.monitor_reaction,
                                              random.Random(self._mon_rng.random()))
        return ent

    def schedule_log(self, t: int, e: Edge) -> None:
        self.log_events.append((t, "edge", e))

    def schedule_payout(self, t: int, custodian: str, acct: str, signer_kid: str) -> None:
        self.log_events.append((t, "payout", (custodian, acct, signer_kid)))

    def bind_domain(self, domain: str, ent: LegalEntity, t: int, verifier: Optional[DomainVerifier] = None) -> Edge:
        dv = verifier or self.dv
        val = dv.challenge(domain, ent.rep)
        self.dns.setdefault(f"_meridian-challenge.{domain}", []).append(val)
        e = dv.bind(domain, ent, self.dns, t, t + EDGE_LIFETIME)
        assert e is not None
        self.schedule_log(t, e)
        return e

    def terminal(self, ent: LegalEntity, t: int, bank_name: Optional[str] = None) -> Tuple[str, Edge, Bank]:
        bank = self.banks[bank_name or BANK_FOR_GEO.get(ent.jurisdiction, "bnkus1")]
        acct = bank.open_account(ent)
        self.owner[acct] = ent.lei
        te = bank.terminal_binding(acct, t, t + EDGE_LIFETIME)
        self.schedule_log(t, te)
        return acct, te, bank

    def watch(self, ent: LegalEntity, processing: Set[str] = frozenset(), accounts: Set[str] = frozenset(),
              domains: Set[str] = frozenset()) -> None:
        m = self.monitors.get(ent.lei)
        if m is not None:
            m.own_processing |= set(processing)
            m.own_accounts |= set(accounts)
            m.domains |= set(domains)

    # ------------------------------------------------------------ structures
    def _direct_psp(self, br: BrandRecord, ent: LegalEntity, t: int, sc: Scope, structure: str,
                    psp_name: Optional[str] = None, rails=None) -> RouteTemplate:
        psp = self.psps[psp_name or self.rng.choice(sorted(self.psps))]
        p = psp.new_account()
        e1 = psp.issue(AG, ent.lei_id, p, sc, t, t + EDGE_LIFETIME, psp.key, signing_key=ent.rep)
        self.schedule_log(t, e1)
        acct, te, _ = self.terminal(ent, t)
        self.schedule_payout(t, p, acct, psp.key.kid)
        self.watch(ent, {p}, {acct})
        e0 = self.brand_edge(br)
        return RouteTemplate(self.next_id("rt"), br.brand_id, structure, rails or STRUCTURE_RAILS[structure],
                             [e0, e1], p, psp.key, [], [(p, psp.key)], acct, te, sc.meet(e0.scope),
                             ent.lei, ent.name, psp.name)

    def brand_edge(self, br: BrandRecord) -> Edge:
        return self._brand_edges[br.brand_id]

    def add_brand(self, name: str, structure: str, t: int, category: Optional[str] = None,
                  geo: Optional[str] = None, entity: Optional[LegalEntity] = None, domain: Optional[str] = None,
                  genuine: bool = True, monitored: bool = True, verifier: Optional[DomainVerifier] = None,
                  log_offset: int = 0, display: Optional[str] = None) -> BrandRecord:
        rng = self.rng
        category = category or rng.choice(sorted(MCC_BY_CATEGORY))
        geo = geo or rng.choice(["US", "US", "US", "GB", "DE", "FR", "IN", "NL"])
        domain = domain or f"{name.lower()}.{'co.uk' if geo == 'GB' else 'in' if geo == 'IN' else 'com'}"
        bid = f"brand:{domain}"
        suffix = {"US": "Inc", "GB": "Ltd", "DE": "GmbH", "FR": "SAS", "IN": "Pvt Ltd", "NL": "B.V."}.get(geo, "Inc")
        ent = entity or self.new_entity(f"{display or name} {suffix}", geo, t, monitored, {domain})
        if entity is not None:
            self.watch(ent, domains={domain})
        color = tuple(rng.randrange(30, 220) for _ in range(3))
        br = BrandRecord(bid, display or name, domain, ent, structure, category, geo, GEO_CUR[geo],
                         logo_hash=phash(render_logo(display or name, color)), color=color, first_seen=t,
                         genuine=genuine)
        self.brands[bid] = br
        if structure != "S11":
            self._brand_edges[bid] = self.bind_domain(domain, ent, t + log_offset, verifier)
        self.registry.add(Candidate(bid, br.name, domain, ent.lei, br.logo_hash,
                                    f"{br.name} {category} store", t, geo))
        return br

    def build_structure(self, br: BrandRecord, t: int) -> None:
        s = br.structure
        ent = br.entity
        rng = self.rng
        cur, geo, mcc = br.currency, br.geo, br.mcc
        base = Scope.make(currencies={cur}, mccs={mcc}, ceiling=2_000_000)
        T = []
        if s in ("S1", "S9", "S10"):
            T.append(self._direct_psp(br, ent, t, base.meet(Scope.make(rails={"card", "psp_token", "wallet"})), s,
                                      rails=STRUCTURE_RAILS[s]))
        elif s == "S2":
            acct, te, bank = self.terminal(ent, t)
            self.watch(ent, accounts={acct})
            e0 = self.brand_edge(br)
            T.append(RouteTemplate(self.next_id("rt"), br.brand_id, s, STRUCTURE_RAILS[s], [e0, te], acct, ent.rep,
                                   [], [], acct, te, base.meet(Scope.make(rails={"a2a_instant"})), ent.lei, ent.name,
                                   bank.name))
        elif s in ("S3", "S7"):
            plat = self.agentplat if s == "S7" else self.marketplaces[rng.choice(sorted(self.marketplaces))]
            sc = base.meet(Scope.make(rails={"card", "psp_token"}))
            store = plat.new_account("store", ns=f"mor:{plat.name}")
            e1 = plat.issue(AG, ent.lei_id, store, sc, t, t + EDGE_LIFETIME, plat.key, delegate=True,
                            signing_key=ent.rep)
            main = f"proc:{plat.name}/main"
            e2 = plat.issue(AG, store, main, sc, t, t + EDGE_LIFETIME, plat.key, delegate=True)
            seller = plat.new_account("seller")
            e3 = plat.issue(SUB, main, seller, sc, t, t + EDGE_LIFETIME, plat.key, subject=ent.lei_id)
            for e in (e1, e2, e3):
                self.schedule_log(t, e)
            acct, te, _ = self.terminal(ent, t)
            self.schedule_payout(t, seller, acct, plat.key.kid)
            self.watch(ent, {seller}, {acct})
            e0 = self.brand_edge(br)
            T.append(RouteTemplate(self.next_id("rt"), br.brand_id, s, STRUCTURE_RAILS[s], [e0, e1, e2], main,
                                   plat.key, [e3], [(main, plat.key), (seller, plat.key)], acct, te,
                                   sc.meet(e0.scope), ent.lei, ent.name, plat.name))
        elif s == "S4":
            pf = self.payfacs[rng.choice(sorted(self.payfacs))]
            sc = base.meet(Scope.make(rails={"card"}))
            sub = pf.new_account("sub")
            e1 = pf.issue(AG, ent.lei_id, sub, sc, t, t + EDGE_LIFETIME, pf.key, signing_key=ent.rep)
            self.schedule_log(t, e1)
            acct, te, _ = self.terminal(ent, t)
            self.schedule_payout(t, sub, acct, pf.key.kid)
            self.watch(ent, {sub}, {acct})
            e0 = self.brand_edge(br)
            T.append(RouteTemplate(self.next_id("rt"), br.brand_id, s, STRUCTURE_RAILS[s], [e0, e1], sub, pf.key,
                                   [], [(sub, pf.key)], acct, te, sc.meet(e0.scope), ent.lei, ent.name, pf.name))
        elif s in ("S5", "S8"):
            # S5: licensed reseller as merchant of record, limited to one
            # geography and a ceiling. S8: franchisees, one per region.
            regions = [geo] if s == "S5" else sorted({geo, *rng.sample(["US", "GB", "DE", "FR", "NL"], 2)})
            for reg in regions:
                rname = f"{br.name} {'Reseller' if s == 'S5' else 'Franchise ' + reg}"
                rent = self.new_entity(f"{rname} Ltd", reg, t)
                cur_r = GEO_CUR[reg]
                sc = Scope.make(rails={"card", "psp_token"}, currencies={cur_r}, mccs={mcc}, geos={reg},
                                ceiling=500_000 if s == "S5" else 2_000_000)
                ei = self.entity_issuers[ent.lei]
                e1 = ei.issue(ASG, ent.lei_id, rent.lei_id, sc, t, t + EDGE_LIFETIME, rent.rep)
                self.schedule_log(t, e1)
                psp = self.psps[rng.choice(sorted(self.psps))]
                p = psp.new_account()
                e2 = psp.issue(AG, rent.lei_id, p, sc, t, t + EDGE_LIFETIME, psp.key, signing_key=rent.rep)
                self.schedule_log(t, e2)
                acct, te, _ = self.terminal(rent, t)
                self.schedule_payout(t, p, acct, psp.key.kid)
                self.watch(rent, {p}, {acct})
                e0 = self.brand_edge(br)
                T.append(RouteTemplate(self.next_id("rt"), br.brand_id, s, STRUCTURE_RAILS[s], [e0, e1, e2], p,
                                       psp.key, [], [(p, psp.key)], acct, te, sc.meet(e0.scope), rent.lei,
                                       rent.name, psp.name))
        elif s == "S6":
            T.append(self._direct_psp(br, ent, t, base.meet(Scope.make(rails={"card", "psp_token"})), "S1",
                                      rails=("card", "psp_token")))
            lender = self._lender(t)
            sc = Scope.make(rails={"bnpl"}, currencies={cur}, mccs={mcc}, ceiling=300_000)
            ei = self.entity_issuers[ent.lei]
            e1 = ei.issue(ASG, ent.lei_id, lender["ent"].lei_id, sc, t, t + EDGE_LIFETIME, lender["ent"].rep)
            self.schedule_log(t, e1)
            e0 = self.brand_edge(br)
            T.append(RouteTemplate(self.next_id("rt"), br.brand_id, s, ("bnpl",), [e0, e1, lender["edge"]],
                                   lender["p"], lender["psp"].key, [], [(lender["p"], lender["psp"].key)],
                                   lender["acct"], lender["te"], sc.meet(e0.scope), lender["ent"].lei,
                                   lender["ent"].name, lender["psp"].name))
        elif s == "S11":
            bank = self.banks[BANK_FOR_GEO.get(geo, "bnkus1")]
            acct = bank.open_account(ent)
            self.owner[acct] = ent.lei
            # no credentials at all: the merchant cannot present a path
            T.append(RouteTemplate(self.next_id("rt"), br.brand_id, s, STRUCTURE_RAILS[s], [], acct, ent.rep, [],
                                   [], acct, None, Scope.make(currencies={cur}, mccs={mcc}), ent.lei, ent.name))
        elif s == "S12":
            wkey = KeyPair.from_seed(f"wallet|{br.brand_id}".encode(), ETH)
            addr = chain_address("eip155:84532", wkey.public.address)
            self.trust.add_wallet(addr, wkey.public)
            ei = self.entity_issuers[ent.lei]
            sc = Scope.make(rails={"stablecoin"}, currencies={"USDC"}, mccs={mcc}, ceiling=2_000_000)
            e1 = ei.issue(ID, ent.lei_id, addr, sc, t, t + EDGE_LIFETIME, wkey)
            self.schedule_log(t, e1)
            self.owner[addr] = ent.lei
            br.did_wallets.add(addr)
            self.watch(ent, accounts={addr})
            e0 = self.brand_edge(br)
            T.append(RouteTemplate(self.next_id("rt"), br.brand_id, s, ("stablecoin",), [e0, e1], addr, wkey, [],
                                   [], addr, e1, sc.meet(e0.scope), ent.lei, ent.name, "self"))
        elif s == "S13":
            sc = base.meet(Scope.make(rails={"card"}))
            vault = self.escrow.new_account("vault")
            e1 = self.escrow.issue(CUS, ent.lei_id, vault, sc, t, t + EDGE_LIFETIME, self.escrow.key,
                              condition="delivery-confirmed", signing_key=ent.rep)
            self.schedule_log(t, e1)
            acct, te, _ = self.terminal(ent, t)
            self.schedule_payout(t, vault, acct, self.escrow.key.kid)
            self.watch(ent, {vault}, {acct})
            e0 = self.brand_edge(br)
            T.append(RouteTemplate(self.next_id("rt"), br.brand_id, s, ("card",), [e0, e1], vault, self.escrow.key,
                                   [], [(vault, self.escrow.key)], acct, te, sc.meet(e0.scope), ent.lei, ent.name,
                                   self.escrow.name))
        br.templates.extend(T)
        for tpl in T:
            self.legit.setdefault(br.brand_id, []).append((tpl.scope, tpl.terminal))

    def _lender(self, t: int) -> dict:
        if not hasattr(self, "_lenders"):
            self._lenders = []
        if len(self._lenders) < 2:
            ent = self.new_entity(f"Lender{len(self._lenders) + 1} Credit Inc", "US", t)
            psp = self.psps["pspone"]
            p = psp.new_account("bnpl")
            sc = Scope.make(rails={"bnpl"})
            e = psp.issue(AG, ent.lei_id, p, sc, t, t + EDGE_LIFETIME, psp.key, signing_key=ent.rep)
            self.schedule_log(t, e)
            acct, te, _ = self.terminal(ent, t)
            self.schedule_payout(t, p, acct, psp.key.kid)
            self.watch(ent, {p}, {acct})
            self._lenders.append({"ent": ent, "p": p, "edge": e, "acct": acct, "te": te, "psp": psp})
        return self.rng.choice(self._lenders)

    # ------------------------------------------------------------ build
    def build(self) -> "World":
        names = unique_brands(self.rng, self.n_brands + 40)
        plan = (["S1"] * 22 + ["S2"] * 10 + ["S3"] * 16 + ["S4"] * 12 + ["S5"] * 8 + ["S6"] * 8 + ["S7"] * 8 +
                ["S8"] * 5 + ["S10"] * 6 + ["S11"] * 6 + ["S12"] * 8 + ["S13"] * 6)
        self.rng.shuffle(plan)
        ni = 0
        for s in plan:
            t0 = self.rng.randrange(1 * DAY, 200 * DAY)
            log_offset = 0
            if s == "S10":
                # onboarded during the experiment window
                t0 = self.rng.randrange(T_EXP_START - 2 * DAY, T_EXP_END - 2 * DAY)
            br = self.add_brand(names[ni], s, t0, log_offset=log_offset)
            ni += 1
            self.build_structure(br, t0)
        # S9: three brands under one group entity
        for g in range(4):
            t0 = self.rng.randrange(1 * DAY, 200 * DAY)
            geo = self.rng.choice(["US", "GB", "DE"])
            group = self.new_entity(f"{names[ni]} Group Holdings", geo, t0)
            for k in range(3):
                br = self.add_brand(names[ni + k + 1], "S9", t0, geo=geo, entity=group)
                self.build_structure(br, t0)
            ni += 4
        # brands that attract impersonation (lookalikes, clones): a fixed
        # seeded subset, so benign step-up cost can be split by exposure
        genuine = sorted(b for b, r in self.brands.items() if r.genuine and r.structure != "S11")
        self.impersonated = set(random.Random(self.seed + 99).sample(genuine, int(0.35 * len(genuine))))
        return self

    # ------------------------------------------------------------ payments
    def legit_terminals(self, brand: str, tup) -> Set[str]:
        return {term for (sc, term) in self.legit.get(brand, []) if sc.contains(tup) and term not in self.compromised}

    def snapshots(self, edges: List[Edge], t: int) -> Dict:
        out = {}
        for e in edges:
            if e.status.list_id not in out:
                out[e.status.list_id] = self.sr.lists[e.status.list_id].snapshot(t)
        return out

    def make_payment(self, tpl: RouteTemplate, rail: str, amount: int, t: int, rng: random.Random,
                     payee: Optional[str] = None, currency: Optional[str] = None, mcc: Optional[str] = None,
                     geo: Optional[str] = None) -> Payment:
        br = self.brands[tpl.brand]
        cur = currency or ("USDC" if rail == "stablecoin" else
                           (sorted(tpl.scope.currencies)[0] if tpl.scope.currencies else br.currency))
        g = geo or (sorted(tpl.scope.geos)[0] if tpl.scope.geos else br.geo)
        pid = f"pay_{rng.getrandbits(48):012x}"
        return Payment(pid, payee or tpl.payee, rail, cur, amount, mcc or br.mcc, g, t,
                       f"cart_{rng.getrandbits(64):016x}", f"n_{rng.getrandbits(64):016x}")

    def bundle_for(self, tpl: RouteTemplate, pay: Payment, snap_t: Optional[int] = None,
                   payout_override: Optional[str] = None, terminal_override: Optional[Edge] = None,
                   commit_override: Optional[Dict[str, str]] = None, drop_commitments: bool = False) -> RouteBundle:
        """The route bundle a merchant/PSP presents for this payment."""
        st = pay.t if snap_t is None else snap_t
        beta = BindingToken.issue(tpl.beta_key, pay)
        rap = RAP(list(tpl.rap_edges), self.snapshots(tpl.rap_edges, st), beta)
        commits: List[Commitment] = []
        if not drop_commitments:
            for i, (h, key) in enumerate(tpl.custodians):
                last = i == len(tpl.custodians) - 1
                nxt = tpl.custodians[i + 1][0] if not last else (payout_override or tpl.terminal)
                if commit_override and h in commit_override:
                    nxt = commit_override[h]
                commits.append(Commitment.issue(key, PAYOUT if last else REMIT, pay, h, nxt, beta.digest))
        term = None
        if tpl.custodians:
            term = terminal_override if terminal_override is not None else tpl.terminal_edge
        extra = list(tpl.onward) + ([term] if term is not None else [])
        return RouteBundle(rap, list(tpl.onward), commits, term, self.snapshots(extra, st))

    def flush_monitors(self, now: int) -> None:
        for m in self.monitors.values():
            m.flush(self.log, now)
