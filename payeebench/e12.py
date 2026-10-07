"""E12: independently authored attacks.

Authors who have not seen the PayeeBench generator write attacks in a small
declarative schema (docs/e12/AUTHORING.md). This module validates a spec and
compiles it into a PayeeBench ``Case`` against a fresh world. The author
chooses the scenario, the victim structure and rail, and the parameters; the
compiler picks nothing about the attack itself except, with a seed derived
from the attack id, which concrete brand and attacker accounts instantiate it.

Nothing here looks at a configuration's decision. Compilation uses world
ground truth only, so an author cannot tune an attack against a result, and
``diverts_if_paid`` tells the harness whether the attack would actually send
the money to the wrong place if every check allowed it.

The schema is versioned. A scenario kind can be added before the attack file
is frozen (and then the schema version and the changelog in
docs/e12/AUTHORING.md change); after the freeze the harness refuses any file
whose hash differs from the lock.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import replace
from typing import Any, Callable, Dict, List, Optional, Tuple

from meridian.core.decision import Payment
from meridian.core.edges import AG
from meridian.core.keys import ETH, KeyPair
from meridian.core.ids import chain_address
from meridian.core.scope import Scope

from .cases import (AttackerKit, Case, Listing, _fake_binding, _reseller, _templates_for, attacker_legal_name,
                    genuine_listing, honest_exec, in_window, pick_amount)
from meridian.cba import phash, render_logo

from .names import TECHNIQUES, lookalike
from .world import DAY, EDGE_LIFETIME, HOUR, T_EXP_END, T_EXP_START, World

SCHEMA = "meridian-e12/1"

RAILS = ("card", "psp_token", "wallet", "a2a_instant", "stablecoin", "bnpl")
USER_WORDS = ("exact", "lowercase", "typo", "abbreviated")

# kind -> (allowed victim structures, allowed rails or None for "whatever the template offers")
KINDS: Dict[str, Tuple[Tuple[str, ...], Optional[Tuple[str, ...]]]] = {
    "lookalike": (("S1", "S2", "S3", "S4", "S9", "S12"), None),
    "payee_swap": (("S1", "S2", "S3", "S4", "S9", "S12", "S13"), None),
    "rogue_submerchant": (("S1", "S3", "S4", "S9"), ("card",)),
    "processor_payout_change": (("S1", "S4", "S9"), ("card",)),
    "custodian_redirect": (("S3", "S7"), None),
    "first_hop_mismatch": (("S1", "S3", "S4", "S7", "S9"), ("card",)),
    "revoked_delegation": (("S1", "S3", "S4", "S9"), ("card",)),
    "scope_abuse": (("S1", "S3", "S4", "S9", "S12"), None),
    "fresh_fake_delegation": (("S1", "S2", "S3", "S4", "S9"), ("card",)),
    "split_view": (("S1", "S3", "S4", "S9"), ("card",)),
    "irreversible_revocation": (("S2", "S12"), ("a2a_instant", "stablecoin")),
}

PARAMS: Dict[str, Dict[str, Tuple]] = {
    # parameter -> allowed values (a tuple of strings), or ("int", lo, hi) / ("bool",)
    "lookalike": {"technique": tuple(TECHNIQUES), "copy_logo": ("bool",)},
    "payee_swap": {"evidence": ("keep", "own", "none"), "channel": ("checkout", "feed", "registry")},
    "rogue_submerchant": {"evidence": ("none", "entity")},
    "processor_payout_change": {"hours_before": ("int", 1, 72)},
    "custodian_redirect": {},
    "first_hop_mismatch": {"variant": ("transaction-laundering", "acquirer-swap")},
    "revoked_delegation": {"seconds_since_revocation": ("int", 1, 20 * DAY), "snapshot": ("stale", "fresh")},
    "scope_abuse": {"dimension": ("geo", "ceiling", "currency", "mcc", "rail")},
    "fresh_fake_delegation": {"wait": ("rush", "patient"), "brand_monitor": ("online", "offline")},
    "split_view": {},
    "irreversible_revocation": {"variant": ("stale-authority", "late-revocation")},
}

LISTING_FLAGS = ("manifest_valid", "curated", "known_bad", "looks_off")
REQUIRED = ("id", "author", "title", "narrative", "victim", "scenario")


class SpecError(ValueError):
    pass


# ------------------------------------------------------------------ validation

def validate_spec(spec: Dict[str, Any]) -> None:
    """Structural validation. Raises SpecError with a message the author can act on."""
    if not isinstance(spec, dict):
        raise SpecError("an attack must be an object")
    aid = spec.get("id", "<no id>")

    def err(msg: str) -> SpecError:
        return SpecError(f"{aid}: {msg}")

    for k in REQUIRED:
        if k not in spec:
            raise err(f"missing field '{k}'")
    if not (isinstance(aid, str) and aid and all(ch.isalnum() or ch in "-_" for ch in aid)):
        raise err("id must be a non-empty string of letters, digits, '-' and '_'")

    for k in ("author", "title"):
        if not (isinstance(spec[k], str) and spec[k].strip()):
            raise err(f"'{k}' must be a non-empty string")
    if not (isinstance(spec["narrative"], str) and len(spec["narrative"].strip()) >= 40):
        raise err("'narrative' must say in at least 40 characters what the attacker does and why it should work")
    v, sc = spec["victim"], spec["scenario"]
    if not isinstance(v, dict) or "structure" not in v or "rail" not in v:
        raise err("'victim' needs 'structure' and 'rail'")
    if not isinstance(sc, dict) or "kind" not in sc:
        raise err("'scenario' needs 'kind'")
    kind = sc["kind"]
    if kind not in KINDS:
        raise err(f"unknown scenario kind '{kind}'; known: {', '.join(sorted(KINDS))}")
    structs, rails = KINDS[kind]
    if v["structure"] not in structs:
        raise err(f"scenario '{kind}' supports victim structures {list(structs)}")
    if v["rail"] not in RAILS:
        raise err(f"victim rail must be one of {list(RAILS)}")
    if rails is not None and v["rail"] not in rails:
        raise err(f"scenario '{kind}' supports victim rails {list(rails)}")
    if kind == "irreversible_revocation" and (v["structure"], v["rail"]) not in (("S2", "a2a_instant"),
                                                                                ("S12", "stablecoin")):
        raise err("irreversible_revocation needs S2 with a2a_instant or S12 with stablecoin")
    allowed = PARAMS[kind]
    for p, val in sc.items():
        if p == "kind":
            continue
        if p not in allowed:
            raise err(f"scenario '{kind}' has no parameter '{p}'; known: {sorted(allowed)}")
        spec_p = allowed[p]
        if spec_p == ("bool",):
            if not isinstance(val, bool):
                raise err(f"'{p}' must be true or false")
        elif spec_p[0] == "int":
            if not (isinstance(val, int) and not isinstance(val, bool) and spec_p[1] <= val <= spec_p[2]):
                raise err(f"'{p}' must be an integer between {spec_p[1]} and {spec_p[2]}")
        elif val not in spec_p:
            raise err(f"'{p}' must be one of {list(spec_p)}")
    lst = spec.get("listing", {})
    if not isinstance(lst, dict) or any(k not in LISTING_FLAGS or not isinstance(x, bool) for k, x in lst.items()):
        raise err(f"'listing' may only set booleans among {list(LISTING_FLAGS)}")
    if spec.get("user_words", "exact") not in USER_WORDS:
        raise err(f"'user_words' must be one of {list(USER_WORDS)}")
    amt = spec.get("amount_cents")
    if amt is not None and not (isinstance(amt, int) and not isinstance(amt, bool) and 100 <= amt <= 5_000_000):
        raise err("'amount_cents' must be an integer between 100 and 5000000")
    ck = spec.get("checkout", {})
    if not isinstance(ck, dict) or set(ck) - {"swap_after_mandate"} or \
            any(not isinstance(x, bool) for x in ck.values()):
        raise err("'checkout' may only set the boolean 'swap_after_mandate'")
    for k in ("premise_violation", "user_confirms_stepup"):
        if k in spec and not isinstance(spec[k], bool):
            raise err(f"'{k}' must be true or false")
    extra = set(spec) - set(REQUIRED) - {"listing", "user_words", "amount_cents", "checkout", "premise_violation",
                                         "user_confirms_stepup"}
    if extra:
        raise err(f"unknown fields {sorted(extra)}")


def validate_file(doc: Dict[str, Any], min_attacks: int = 0, min_authors: int = 0) -> List[str]:
    """Validate an attack file; returns the list of problems (empty if fine)."""
    problems: List[str] = []
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return [f"top-level 'schema' must be '{SCHEMA}'"]
    attacks = doc.get("attacks")
    if not isinstance(attacks, list):
        return ["'attacks' must be a list"]
    unknown = set(doc) - {"schema", "attacks", "unexpressible"}
    if unknown:
        return [f"unknown top-level fields {sorted(unknown)}"]
    seen = set()
    for a in attacks:
        try:
            validate_spec(a)
        except SpecError as e:
            problems.append(str(e))
            continue
        if a["id"] in seen:
            problems.append(f"{a['id']}: duplicate id")
        seen.add(a["id"])
    if len(attacks) < min_attacks:
        problems.append(f"{len(attacks)} attacks; at least {min_attacks} are required")
    authors = {a.get("author") for a in attacks if isinstance(a, dict)}
    if len(authors) < min_authors:
        problems.append(f"{len(authors)} distinct authors; at least {min_authors} are required")
    return problems


# ------------------------------------------------------------------ compilation helpers

def _rng(world: World, aid: str) -> random.Random:
    h = hashlib.sha256(f"{world.seed}|{aid}".encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def _pick_victim(world: World, rng: random.Random, spec: Dict[str, Any], need_impersonated: bool = False):
    v = spec["victim"]
    items = [(b, t) for b, t in _templates_for(world, {v["structure"]}) if v["rail"] in t.rails and
             (t.scope.rails is None or v["rail"] in t.scope.rails)]
    if need_impersonated:
        imp = [(b, t) for b, t in items if b.brand_id in world.impersonated]
        items = imp or items
    if not items:
        raise SpecError(f"{spec['id']}: the world has no victim with structure {v['structure']} and rail {v['rail']}")
    return rng.choice(items)


def _amount(spec: Dict[str, Any], rng: random.Random, scope: Scope) -> int:
    return int(spec["amount_cents"]) if spec.get("amount_cents") else pick_amount(rng, scope)


def _t(rng: random.Random) -> int:
    return in_window(rng)


def _words(br, rng: random.Random, style: str) -> str:
    n = br.name
    if style == "lowercase":
        return n.lower()
    if style == "typo" and len(n) > 4:
        i = rng.randrange(1, len(n) - 1)
        return n[:i] + n[i + 1:]
    if style == "abbreviated":
        return n[:max(3, len(n) - 2)]
    return n


def _swap_payment(orig: Payment, payee: str, rail: str, t: int) -> Payment:
    return Payment(orig.payment_id, payee, orig.rail, "USDC" if rail == "stablecoin" else orig.currency,
                   orig.amount, orig.mcc, orig.geo, t, orig.cart_digest, orig.nonce)


# ------------------------------------------------------------------ builders

def _b_lookalike(world, kit, rng, spec) -> Case:
    sc = spec["scenario"]
    br, tpl = _pick_victim(world, rng, spec, need_impersonated=True)
    rail = spec["victim"]["rail"]
    t = _t(rng)
    for _ in range(50):
        disp, dom = lookalike(br.name, br.domain, sc.get("technique", "homoglyph"), rng)
        if dom != br.domain and dom.lower() not in {b.domain for b in world.brands.values()}:
            break
    else:
        raise SpecError(f"{spec['id']}: could not form a lookalike with technique {sc.get('technique')}")
    att = kit.merchant(disp.replace(" ", ""), dom, t - rng.randrange(2 * DAY, 60 * DAY), rail,
                       legal=attacker_legal_name(br, rng), display=disp, geo=br.geo, category=br.category)
    if sc.get("copy_logo", True):
        att.logo_hash = phash(render_logo(br.name, br.color, seed=rng.randrange(10 ** 6), jitter=0.4))
    cand = world.registry.by_id[att.brand_id]
    cand.logo_hash = att.logo_hash
    cand.description = f"{br.name} {br.category} store"
    atpl = att.templates[0]
    r = rail if rail in atpl.rails else atpl.rails[0]
    pay = world.make_payment(atpl, r, _amount(spec, rng, atpl.scope), t, rng)
    bundle = world.bundle_for(atpl, pay)
    lst = Listing(att.brand_id, disp, dom, att.entity.name, att.entity.lei, manifest_valid=True, curated=False,
                  known_bad=False, looks_off=True, did_wallets=set(att.did_wallets), candidate=cand)
    return Case(spec["id"], "E12", "lookalike", br.structure, pay.rail, br.brand_id, br.name, lst, pay, bundle,
                *honest_exec(atpl), template=atpl, vop_name=att.entity.name)


def _b_payee_swap(world, kit, rng, spec) -> Case:
    sc = spec["scenario"]
    br, tpl = _pick_victim(world, rng, spec)
    rail = spec["victim"]["rail"]
    t = _t(rng)
    att = kit.merchant(f"Px{rng.randrange(10 ** 6)}", f"px{rng.randrange(10 ** 8)}.com",
                       t - rng.randrange(DAY, 30 * DAY), rail, legal=attacker_legal_name(br, rng), geo=br.geo,
                       category=br.category)
    atpl = att.templates[0]
    orig = world.make_payment(tpl, rail, _amount(spec, rng, tpl.scope), t, rng)
    pay = _swap_payment(orig, atpl.payee, rail, t)
    ev = sc.get("evidence", "none")
    bundle = (world.bundle_for(tpl, orig) if ev == "keep" else
              world.bundle_for(atpl, pay) if ev == "own" else None)
    return Case(spec["id"], "E12", f"payee_swap:{ev}", br.structure, rail, br.brand_id, br.name,
                genuine_listing(br, rng), pay, bundle, *honest_exec(atpl), template=tpl, vop_name=att.entity.name)


def _b_rogue_sub(world, kit, rng, spec) -> Case:
    sc = spec["scenario"]
    br, tpl = _pick_victim(world, rng, spec)
    t = _t(rng)
    pf = world.payfacs[rng.choice(sorted(world.payfacs))]
    ent = kit.entity(attacker_legal_name(br, rng), t - rng.randrange(DAY, 30 * DAY), br.geo)
    sub = pf.new_account("sub")
    e = pf.issue(AG, ent.lei_id, sub, Scope.make(rails={"card"}), ent.registered_at, ent.registered_at + EDGE_LIFETIME,
                 pf.key, signing_key=ent.rep)
    world.schedule_log(ent.registered_at, e)
    acct, te, _ = world.terminal(ent, ent.registered_at)
    world.schedule_payout(ent.registered_at, sub, acct, pf.key.kid)
    from .world import RouteTemplate
    atpl = RouteTemplate(world.next_id("rt"), "", "S4", ("card",), [e], sub, pf.key, [], [(sub, pf.key)], acct, te,
                         Scope.make(rails={"card"}), ent.lei, ent.name, pf.name)
    pay = world.make_payment(tpl, "card", _amount(spec, rng, tpl.scope), t, rng, payee=sub)
    ev = sc.get("evidence", "none")
    bundle = None if ev == "none" else world.bundle_for(atpl, pay)
    lst = Listing(br.brand_id, br.name, f"{pf.name}.example", ent.name, ent.lei, manifest_valid=True, curated=True)
    return Case(spec["id"], "E12", f"rogue_submerchant:{ev}", br.structure, "card", br.brand_id, br.name, lst, pay,
                bundle, *honest_exec(atpl), template=atpl, vop_name=ent.name)


def _b_payout_change(world, kit, rng, spec) -> Case:
    sc = spec["scenario"]
    br, tpl = _pick_victim(world, rng, spec)
    t = _t(rng)
    mule = kit.entity(rng.choice(["Mule Holdings LLC", "Quick Settle Ltd", "Harbor Supply LLC"]), t - 40 * DAY)
    t_change = t - int(sc.get("hours_before", 12)) * HOUR
    acct, te, _ = world.terminal(mule, t - 40 * DAY)
    world.schedule_payout(t_change, tpl.payee, acct, tpl.custodians[-1][1].kid)
    pay = world.make_payment(tpl, "card", _amount(spec, rng, tpl.scope), t, rng)
    bundle = world.bundle_for(tpl, pay, payout_override=acct, terminal_override=te)
    hops = [(tpl.payee, acct, tpl.custodians[-1][1])]
    return Case(spec["id"], "E12", "processor_payout_change", br.structure, "card", br.brand_id, br.name,
                genuine_listing(br, rng), pay, bundle, tpl.payee, hops, acct, template=tpl,
                vop_name=tpl.merchant_name)


def _b_custodian_redirect(world, kit, rng, spec) -> Case:
    br, tpl = _pick_victim(world, rng, spec)
    if not tpl.custodians:
        raise SpecError(f"{spec['id']}: the victim route has no custodian that could redirect")
    t = _t(rng)
    ent = kit.entity("Insider Payouts LLC", t - 60 * DAY)
    acct, _, _ = world.terminal(ent, t - 60 * DAY)
    rail = spec["victim"]["rail"]
    pay = world.make_payment(tpl, rail, _amount(spec, rng, tpl.scope), t, rng)
    bundle = world.bundle_for(tpl, pay)
    main, key = tpl.custodians[0]
    return Case(spec["id"], "E12", "custodian_redirect", br.structure, rail, br.brand_id, br.name,
                genuine_listing(br, rng), pay, bundle, tpl.payee, [(main, acct, key)], acct, template=tpl,
                vop_name=tpl.merchant_name)


def _b_first_hop(world, kit, rng, spec) -> Case:
    sc = spec["scenario"]
    br, tpl = _pick_victim(world, rng, spec)
    t = _t(rng)
    ent = kit.entity(rng.choice(["Laundry Retail LLC", "Mirror Goods Ltd", "Proxy Trading LLC"]), t - 60 * DAY)
    p2, _, acct2, _, psp2 = kit.psp_account(ent, t - 60 * DAY)
    pay = world.make_payment(tpl, "card", _amount(spec, rng, tpl.scope), t, rng)
    bundle = world.bundle_for(tpl, pay)
    variant = sc.get("variant", "transaction-laundering")
    return Case(spec["id"], "E12", f"first_hop_mismatch:{variant}", br.structure, "card", br.brand_id, br.name,
                genuine_listing(br, rng), pay, bundle, p2, [(p2, acct2, psp2.key)], acct2, template=tpl,
                receipt_visible=(variant == "transaction-laundering"), vop_name=tpl.merchant_name)


def _brand_for(world, rng, spec):
    cands = [b for b in world.brands.values() if b.genuine and b.structure == spec["victim"]["structure"]]
    if not cands:
        raise SpecError(f"{spec['id']}: the world has no genuine brand with structure {spec['victim']['structure']}")
    return rng.choice(cands)


def _b_revoked(world, kit, rng, spec) -> Case:
    sc = spec["scenario"]
    br = _brand_for(world, rng, spec)
    t = _t(rng)
    scope = Scope.make(rails={"card", "psp_token"}, currencies={br.currency}, mccs={br.mcc}, geos={br.geo},
                       ceiling=500_000)
    tpl, e1, ei = _reseller(world, br, t - 200 * DAY, rng, scope, f"{br.name} Former Reseller Ltd")
    t_rev = t - int(sc.get("seconds_since_revocation", 5 * DAY))
    ei.status_list.revoke(e1.status.index, t_rev)
    world.legit.setdefault(br.brand_id, [])
    pay = world.make_payment(tpl, "card", _amount(spec, rng, tpl.scope), t, rng)
    snap_t = t_rev - 60 if sc.get("snapshot", "stale") == "stale" else t
    bundle = world.bundle_for(tpl, pay, snap_t=snap_t)
    return Case(spec["id"], "E12", f"revoked_delegation:{sc.get('snapshot', 'stale')}", br.structure, "card",
                br.brand_id, br.name, genuine_listing(br, rng), pay, bundle, *honest_exec(tpl), template=tpl,
                vop_name=tpl.merchant_name)


def _b_scope(world, kit, rng, spec) -> Case:
    sc = spec["scenario"]
    br = _brand_for(world, rng, spec)
    t = _t(rng)
    scope = Scope.make(rails={"card"}, currencies={br.currency}, mccs={br.mcc}, geos={br.geo}, ceiling=300_000)
    tpl, _, _ = _reseller(world, br, t - 100 * DAY, rng, scope, f"{br.name} Licensed Reseller Ltd")
    world.legit.setdefault(br.brand_id, []).append((tpl.scope, tpl.terminal))
    dim = sc.get("dimension", "geo")
    kw: Dict[str, Any] = {}
    amt = _amount(spec, rng, tpl.scope)
    rail = "card"
    if dim == "geo":
        kw["geo"] = "GB" if br.geo != "GB" else "DE"
    elif dim == "ceiling":
        amt = max(amt, 300_000 + rng.randrange(1000, 500_000))
    elif dim == "currency":
        kw["currency"] = "EUR" if br.currency != "EUR" else "GBP"
    elif dim == "mcc":
        kw["mcc"] = "5732" if br.mcc != "5732" else "5942"
    else:
        rail = "psp_token"
    pay = world.make_payment(tpl, rail, amt, t, rng, **kw)
    bundle = world.bundle_for(tpl, pay)
    return Case(spec["id"], "E12", f"scope_abuse:{dim}", br.structure, rail, br.brand_id, br.name,
                genuine_listing(br, rng), pay, bundle, *honest_exec(tpl), template=tpl, vop_name=tpl.merchant_name)


def _b_fresh_fake(world, kit, rng, spec) -> Case:
    sc = spec["scenario"]
    br = _brand_for(world, rng, spec)
    t_fake = in_window(rng, T_EXP_START - 20 * DAY, T_EXP_END - 20 * DAY)
    tpl, fake, ent = _fake_binding(world, kit, rng, br, t_fake)
    offline = sc.get("brand_monitor", "online") == "offline"
    if offline:
        world.monitors[br.entity.lei].ignore_refs.add(fake.eid)
        d = world.delta + rng.randrange(HOUR, 3 * DAY)
    elif sc.get("wait", "rush") == "patient":
        d = world.delta + rng.randrange(HOUR, 3 * HOUR)
    else:
        d = int(rng.lognormvariate(10.3, 1.2))
    t = t_fake + max(600, d)
    pay = world.make_payment(tpl, "card", _amount(spec, rng, Scope.make(ceiling=200_000)), t, rng,
                             currency=br.currency, mcc=br.mcc, geo=br.geo)
    bundle = world.bundle_for(tpl, pay)
    lst = Listing(br.brand_id, br.name, br.domain, ent.name, ent.lei, manifest_valid=True, curated=True)
    return Case(spec["id"], "E12", f"fresh_fake_delegation:{sc.get('wait', 'rush')}", br.structure, "card",
                br.brand_id, br.name, lst, pay, bundle, *honest_exec(tpl), template=tpl, premise_violation=offline,
                vop_name=ent.name)


def _b_split_view(world, kit, rng, spec) -> Case:
    br = _brand_for(world, rng, spec)
    t_fork = in_window(rng, T_EXP_START - 20 * DAY, T_EXP_END - 20 * DAY)
    tpl, fake, ent = _fake_binding(world, kit, rng, br, t_fork, log=False)
    t = t_fork + world.delta + rng.randrange(HOUR, 2 * DAY)
    pay = world.make_payment(tpl, "card", _amount(spec, rng, Scope.make(ceiling=200_000)), t, rng,
                             currency=br.currency, mcc=br.mcc, geo=br.geo)
    bundle = world.bundle_for(tpl, pay)
    lst = Listing(br.brand_id, br.name, br.domain, ent.name, ent.lei, manifest_valid=True)
    return Case(spec["id"], "E12", "split_view", br.structure, "card", br.brand_id, br.name, lst, pay, bundle,
                *honest_exec(tpl), template=tpl, log_view=f"fork-{spec['id']}", fork_at=t_fork,
                fork_edges=[(t_fork, fake)], vop_name=ent.name)


def _b_irreversible(world, kit, rng, spec) -> Case:
    sc = spec["scenario"]
    rail = spec["victim"]["rail"]
    br = _brand_for(world, rng, spec)
    t = _t(rng)
    t0 = t - 120 * DAY
    ent = br.entity
    ei = world.entity_issuers[ent.lei]
    from .world import RouteTemplate
    if rail == "a2a_instant":
        acct, te, bank = world.terminal(ent, t0)
        issuer, payee, beta_key, edge = bank, acct, ent.rep, te
    else:
        wkey = KeyPair(ETH)
        payee = chain_address("eip155:84532", wkey.public.address)
        world.trust.add_wallet(payee, wkey.public)
        world.owner[payee] = ent.lei
        scp = Scope.make(rails={"stablecoin"}, currencies={"USDC"}, mccs={br.mcc}, ceiling=2_000_000)
        from meridian.core.edges import ID
        edge = ei.issue(ID, ent.lei_id, payee, scp, t0, t0 + EDGE_LIFETIME, wkey)
        world.schedule_log(t0, edge)
        issuer, beta_key = ei, wkey
    tpl = RouteTemplate(world.next_id("rt"), br.brand_id, br.structure, (rail,), [world.brand_edge(br), edge], payee,
                        beta_key, [], [], payee, edge, edge.scope.meet(world.brand_edge(br).scope), ent.lei, ent.name)
    variant = sc.get("variant", "stale-authority")
    rho = 300
    late = None
    if variant == "stale-authority":
        t_rev = t - rng.randrange(10, rho)
        issuer.status_list.revoke(edge.status.index, t_rev)
        snap_t = t_rev - 1
    else:
        t_rev = t + rng.randrange(30, 400)
        issuer.status_list.revoke(edge.status.index, t_rev)
        snap_t = t
        late = float(t_rev - t + rng.randrange(1, 20))
    pay = world.make_payment(tpl, rail, _amount(spec, rng, tpl.scope), t, rng)
    bundle = world.bundle_for(tpl, pay, snap_t=snap_t)
    world.compromised.add(payee)
    return Case(spec["id"], "E12", f"irreversible_revocation:{variant}", br.structure, rail, br.brand_id, br.name,
                genuine_listing(br, rng), pay, bundle, payee, [], payee, template=tpl, late_evidence_after=late,
                vop_name=ent.name, notes="terminal account compromised (attacker-controlled)")


BUILDERS: Dict[str, Callable] = {
    "lookalike": _b_lookalike, "payee_swap": _b_payee_swap, "rogue_submerchant": _b_rogue_sub,
    "processor_payout_change": _b_payout_change, "custodian_redirect": _b_custodian_redirect,
    "first_hop_mismatch": _b_first_hop, "revoked_delegation": _b_revoked, "scope_abuse": _b_scope,
    "fresh_fake_delegation": _b_fresh_fake, "split_view": _b_split_view, "irreversible_revocation": _b_irreversible,
}


# ------------------------------------------------------------------ compile

def diverts_if_paid(world: World, case: Case) -> bool:
    """Ground truth only: would the money reach a terminal that is not
    legitimate for the intended brand if every check allowed the payment?"""
    return case.exec_terminal not in world.legit_terminals(case.intended, case.payment.tuple)


def compile_attacks(world: World, specs: List[Dict[str, Any]], seed: int = 0,
                    errors: Optional[List[str]] = None) -> List[Case]:
    """Compile validated specs, in file order, into cases on ``world``. With an
    ``errors`` list, an attack that cannot be built is reported there and
    skipped; without one the first problem raises."""
    kit = AttackerKit(world, random.Random(seed * 7919 + 1))
    out: List[Case] = []
    for spec in specs:
        validate_spec(spec)
        rng = _rng(world, spec["id"])
        try:
            case = BUILDERS[spec["scenario"]["kind"]](world, kit, rng, spec)
        except Exception as e:  # a builder that cannot realise the combination in this world
            err = e if isinstance(e, SpecError) else SpecError(
                f"{spec['id']}: cannot be built in this world ({type(e).__name__}: {e})")
            if errors is None:
                raise err from e
            errors.append(str(err))
            continue
        for k, val in spec.get("listing", {}).items():
            setattr(case.listing, k, val)
        case.user_words = _words(world.brands[case.intended], rng, spec.get("user_words", "exact"))
        if spec.get("checkout", {}).get("swap_after_mandate"):
            case.swap_after_mandate = True
        case.premise_violation = case.premise_violation or bool(spec.get("premise_violation"))
        case.user_confirms_stepup = bool(spec.get("user_confirms_stepup"))
        case.notes = f"{spec['author']}: {spec['title']}"
        out.append(case)
    return out
