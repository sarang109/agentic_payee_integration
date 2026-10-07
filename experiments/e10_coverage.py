"""E10 coverage in the wild (passive measurement only).

For top online retailers per market (US, UK, EU, India) we check which
receiving-authority edges could be built today from public or KYB-attestable
data:

  L0->L1  domain to legal entity: the domain resolves and an organisation
          identity is available (OV/EV certificate organisation, or an
          ISSUED LEI found in GLEIF for the retailer's legal name)
  mark    verified mark: BIMI record with a VMC (a= tag)
  L1      LEI exists and is ISSUED (prerequisite for vLEI)
  L1->L2/3 platform or PSP identifiable from the public storefront
  L1->L4  terminal binding by the bank: Verification / Confirmation of Payee
          available in the market (policy-level, cited in the table)

Also: lookalike prevalence (registered dnstwist-style permutations).
One request per site (homepage) with an identifying user agent, DNS and TLS
handshakes, and GLEIF API calls; all responses are cached under
results/cache so reruns do not touch live sites again. The retailer list is
curated by hand (market leaders by public rankings) and checked in as
data/retailers.yaml.
"""

from __future__ import annotations

import json
import os
import re
import socket
import ssl
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import certifi
import dns.resolver
import pandas as pd
import yaml

from payeebench.names import lookalike

from .common import QUICK, RESULTS, ROOT, SEED, Timer, write_csv, write_json, write_table
from .stats import fmt_rate

CACHE = os.path.join(RESULTS, "cache", "e10")
os.makedirs(CACHE, exist_ok=True)
UA = "MERIDIAN-research-measurement/0.2 (passive; one request per site)"
TLS = ssl.create_default_context(cafile=certifi.where())

PSP_MARKERS = {
    "Stripe": ["js.stripe.com", "stripe.network"], "Adyen": ["adyen.com", "adyenpayments"],
    "Braintree": ["braintreegateway.com", "braintree-api.com"], "PayPal": ["paypal.com/sdk", "paypalobjects.com"],
    "Checkout.com": ["checkout.com/js", "frames.checkout.com"], "Klarna": ["klarna.com", "klarnaservices"],
    "Afterpay/Clearpay": ["afterpay.com", "clearpay.co.uk"], "Affirm": ["affirm.com"], "Razorpay": ["razorpay.com"],
    "Paytm": ["paytm.com", "paytm.in"], "PayU": ["payu.in", "payumoney", "secure.payu"], "Juspay": ["juspay.in"],
    "Worldpay": ["worldpay.com"], "Cybersource": ["cybersource.com"], "Amazon Pay": ["payments-amazon.com"],
    "Google Pay": ["pay.google.com"],
}
PLATFORM_MARKERS = {"Shopify": ["cdn.shopify.com", "myshopify.com"], "Salesforce Commerce Cloud": ["demandware.static",
                    "demandware.net"], "SAP Commerce": ["hybris"], "Adobe Commerce/Magento": ["mage/cookies",
                    "magento_", "x-magento"], "BigCommerce": ["bigcommerce.com"], "VTEX": ["vteximg", "vtexassets"]}
STOP = {"inc", "ltd", "limited", "plc", "corp", "corporation", "co", "company", "gmbh", "kg", "kgaa", "ag", "se", "sa",
        "sas", "bv", "nv", "ab", "llc", "private", "pvt", "the", "and", "group", "holdings"}
VOP_POLICY = {
    "US": (False, "no national payee-verification scheme for account-to-account transfers"),
    "UK": (True, "Confirmation of Payee (Pay.UK), name-based"),
    "EU": (True, "Verification of Payee mandatory since 9 Oct 2025 (Instant Payments Regulation); LEI/VAT for legal persons"),
    "IN": (True, "beneficiary name validation on UPI/IMPS before payment"),
}
MARKET_COUNTRIES = {"US": ["US"], "UK": ["GB"], "EU": ["DE", "FR", "NL", "ES", "IT", "SE", "IE", "BE", "AT"], "IN": ["IN"]}


def _cache(key: str, fn):
    path = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".json")
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    val = fn()
    with open(path, "w") as fh:
        json.dump(val, fh)
    time.sleep(0.2)  # be gentle with live services
    return val


def dns_info(domain: str) -> Dict:
    r = dns.resolver.Resolver()
    r.lifetime = 4.0
    out = {"a": False, "bimi": None}
    for name in (domain, f"www.{domain}"):
        try:
            r.resolve(name, "A")
            out["a"] = True
            break
        except Exception:
            pass
    try:
        txt = [b"".join(x.strings).decode(errors="replace") for x in r.resolve(f"default._bimi.{domain}", "TXT")]
        out["bimi"] = next((t for t in txt if t.lower().startswith("v=bimi1")), None)
    except Exception:
        pass
    return out


def cert_org(domain: str) -> Optional[str]:
    ctx = TLS
    for host in (f"www.{domain}", domain):
        try:
            with socket.create_connection((host, 443), timeout=6) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as s:
                    cert = s.getpeercert()
            subj = dict(x[0] for x in cert.get("subject", ()))
            return subj.get("organizationName")
        except Exception:
            continue
    return None


def homepage(domain: str) -> Dict:
    for url in (f"https://www.{domain}/", f"https://{domain}/"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=10, context=TLS) as r:
                html = r.read(800_000).decode(errors="replace").lower()
            return {"ok": True, "psp": sorted(k for k, ms in PSP_MARKERS.items() if any(m in html for m in ms)),
                    "platform": sorted(k for k, ms in PLATFORM_MARKERS.items() if any(m in html for m in ms))}
        except Exception as e:
            last = str(e)[:80]
    return {"ok": False, "psp": [], "platform": [], "error": last}


def _norm(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s).lower() if ch.isalnum())


def gleif_raw(query: str, countries: List[str]) -> List[Dict]:
    q = urllib.parse.quote(query)
    out = []
    for c in countries[:3]:
        url = (f"https://api.gleif.org/api/v1/lei-records?filter%5Bfulltext%5D={q}"
               f"&filter%5Bentity.legalAddress.country%5D={c}&page%5Bsize%5D=20")
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.api+json"})
        with urllib.request.urlopen(req, timeout=20, context=TLS) as r:
            for x in json.loads(r.read())["data"]:
                a = x["attributes"]
                out.append({"lei": x["id"], "name": a["entity"]["legalName"]["name"],
                            "country": a["entity"]["legalAddress"]["country"], "status": a["registration"]["status"]})
    return out


def _tokens(s: str) -> set:
    s = unicodedata.normalize("NFKD", s).lower()
    return {t for t in re.findall(r"[a-z0-9]+", s) if t not in STOP}


def match_lei(legal_name: str, records: List[Dict]) -> Optional[Dict]:
    """Best ISSUED record by token Jaccard with the retailer's legal name;
    accepted only when the overlap is substantial (>= 0.6)."""
    want = _tokens(legal_name)
    best, score = None, 0.0
    for r in records:
        if r["status"] != "ISSUED":
            continue
        got = _tokens(r["name"])
        j = len(want & got) / max(1, len(want | got))
        if j > score:
            best, score = r, j
    if best is None or score < 0.6:
        return None
    return {"lei": best["lei"], "legal_name": best["name"], "country": best["country"], "jaccard": round(score, 2)}


def measure(entry: Dict, market: str) -> Dict:
    domain = entry["domain"]
    token = entry.get("token") or domain.split(".")[0]
    d = _cache(f"dns_{domain}", lambda: dns_info(domain))
    org = _cache(f"cert_{domain}", lambda: cert_org(domain))
    hp = _cache(f"home_{domain}", lambda: homepage(domain))
    q = entry.get("legal_name") or org or token
    raw = _cache(f"gleif_{market}_{domain}", lambda: gleif_raw(q, MARKET_COUNTRIES[market]))
    lei = match_lei(q, raw)
    vmc = bool(d.get("bimi") and re.search(r"\ba=https?://", d["bimi"] or ""))
    vop, _ = VOP_POLICY[market]
    l0l1 = d["a"] and bool(org or lei)
    psp = bool(hp["psp"] or hp["platform"])
    return {"market": market, "domain": domain, "resolves": d["a"], "cert_org": org, "bimi": bool(d.get("bimi")),
            "vmc": vmc, "lei": (lei or {}).get("lei"), "lei_name": (lei or {}).get("legal_name"),
            "homepage_ok": hp["ok"], "psp": ",".join(hp["psp"]), "platform": ",".join(hp["platform"]),
            "edge_L0_L1": l0l1, "edge_mark": vmc, "edge_L1_lei": bool(lei), "edge_L1_L2L3": psp,
            "edge_L1_L4": vop, "g1_path": l0l1 and psp, "full_path": l0l1 and psp and vop}


def lookalikes(domain: str, rng, k: int) -> Dict:
    import random

    r = random.Random(f"{SEED}|{domain}")
    cands = set()
    tries = 0
    while len(cands) < k and tries < k * 6:
        tries += 1
        tech = r.choice(["typo-omission", "typo-swap", "typo-repeat", "typo-replace", "tld-swap", "hyphenation",
                         "affix"])
        _, dom = lookalike(domain.split(".")[0].capitalize(), domain, tech, r)
        if dom != domain and dom.isascii():
            cands.add(dom.lower())

    def resolves(dm: str) -> bool:
        res = dns.resolver.Resolver()
        res.lifetime = 3.0
        for rt in ("A", "NS"):
            try:
                res.resolve(dm, rt)
                return True
            except Exception:
                continue
        return False

    cands = sorted(cands)
    hits = _cache(f"look_{domain}_{k}", lambda: {c: resolves(c) for c in cands})
    return {"domain": domain, "generated": len(hits), "registered": sum(hits.values())}


# ------------------------------------------------------------------ sampled storefronts

TRANCO_1M = os.path.join(ROOT, "data", "tranco", "top-1m.csv.zip")  # Tranco list 56WKN (same list as the top 20k)
MARKET_TLDS = {"UK": (".co.uk", ".uk"), "IN": (".in", ".co.in"),
               "EU": (".de", ".fr", ".nl", ".es", ".it", ".se", ".ie", ".be", ".at"), "US": (".com", ".us")}
SHOP_MARKERS = ["add to cart", "add to bag", "add to basket", "in den warenkorb", "warenkorb", "ajouter au panier",
                "panier", "añadir al carrito", "carrito", "aggiungi al carrello", "carrello", "winkelwagen",
                "in winkelmand", "varukorg", "lägg i varukorgen", "checkout", "/cart", "shopping bag", "basket"]
PRODUCT_MARKERS = ['"@type":"product"', '"@type": "product"', '"@type":"offer"', '"@type": "offer"',
                   'itemtype="http://schema.org/product"', 'itemtype="https://schema.org/product"',
                   "og:type\" content=\"product", "pricecurrency", "data-product-id", "product-card", "productcard"]
USD_MARKERS = ['"pricecurrency":"usd"', '"pricecurrency": "usd"', "usd", "$"]


def storefront(domain: str) -> Dict:
    """One homepage request: storefront signals, PSP and platform markers.
    Only extracted features are kept, never page content."""
    for url in (f"https://www.{domain}/", f"https://{domain}/"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=10, context=TLS) as r:
                html = r.read(800_000).decode(errors="replace").lower()
            shop = sorted({m for m in SHOP_MARKERS if m in html})
            prod = sorted({m for m in PRODUCT_MARKERS if m in html})
            return {"ok": True, "shop_markers": len(shop), "product_markers": len(prod),
                    "usd": any(m in html for m in USD_MARKERS[:2]) or bool(re.search(r"\$\s?\d{1,4}(?:[.,]\d{2})\b", html)),
                    "psp": sorted(k for k, ms in PSP_MARKERS.items() if any(m in html for m in ms)),
                    "platform": sorted(k for k, ms in PLATFORM_MARKERS.items() if any(m in html for m in ms))}
        except Exception as e:
            last = str(e)[:80]
    return {"ok": False, "shop_markers": 0, "product_markers": 0, "usd": False, "psp": [], "platform": [],
            "error": last}


def is_storefront(f: Dict, market: str) -> bool:
    ok = f["ok"] and ((f["shop_markers"] >= 1 and f["product_markers"] >= 1) or
                      (f["shop_markers"] >= 2 and bool(f["platform"])))
    return ok and (market != "US" or f["usd"])


def tranco_by_market(max_rank: int = 1_000_000) -> Dict[str, List[tuple]]:
    import zipfile
    out: Dict[str, List[tuple]] = {m: [] for m in MARKET_TLDS}
    with zipfile.ZipFile(TRANCO_1M) as z:
        name = z.namelist()[0]
        for line in z.read(name).decode().splitlines():
            rank, dom = line.strip().split(",", 1)
            if int(rank) > max_rank:
                break
            for m, tlds in MARKET_TLDS.items():
                if dom.endswith(tlds):
                    out[m].append((int(rank), dom))
                    break
    return out


def sample_storefronts(per_market: int, max_candidates: int) -> pd.DataFrame:
    by_m = tranco_by_market()
    rows = []
    for m, cands in by_m.items():
        found, k = 0, 0
        batch = 64
        while found < per_market and k < min(len(cands), max_candidates):
            chunk = cands[k:k + batch]
            k += len(chunk)
            with ThreadPoolExecutor(16) as ex:
                feats = list(ex.map(lambda rd: _cache(f"store_{rd[1]}", lambda: storefront(rd[1])), chunk))
            for (rank, dom), f in zip(chunk, feats):
                sf = is_storefront(f, m)
                rows.append({"market": m, "rank": rank, "domain": dom, "storefront": sf,
                             "shop_markers": f["shop_markers"], "product_markers": f["product_markers"],
                             "fetched": f["ok"]})
                if sf and found < per_market:
                    found += 1
        print(f"  E10b {m}: {found} storefronts among {k} candidates")
    return pd.DataFrame(rows)


def run_e10b(per_market: int, max_candidates: int) -> Dict:
    with Timer(f"E10b sampling storefronts from Tranco ({per_market} per market)"):
        cand = sample_storefronts(per_market, max_candidates)
    write_csv("e10b_candidates", cand)
    picked = cand[cand.storefront].groupby("market").head(per_market)
    jobs = [({"domain": r.domain}, r.market) for r in picked.itertuples()]
    with Timer(f"E10b measuring {len(jobs)} sampled storefronts"):
        with ThreadPoolExecutor(8) as ex:
            rows = list(ex.map(lambda j: measure(*j), jobs))
    df = pd.DataFrame(rows)
    write_csv("e10b_storefronts", df)
    agg = []
    for m, g in df.groupby("market"):
        n = len(g)
        c = cand[cand.market == m]
        agg.append({"market": m, "storefronts": n, "candidates fetched": int(c.fetched.sum()),
                    "Tranco rank range": f"{int(c['rank'].min())}-{int(c['rank'].max())}",
                    "L0->L1 domain to entity": fmt_rate(int(g.edge_L0_L1.sum()), n),
                    "verified mark (VMC)": fmt_rate(int(g.edge_mark.sum()), n),
                    "LEI candidate": fmt_rate(int(g.edge_L1_lei.sum()), n),
                    "platform/PSP identifiable": fmt_rate(int(g.edge_L1_L2L3.sum()), n),
                    "G1 route buildable (no terminal binding)": fmt_rate(int(g.g1_path.sum()), n),
                    "full path buildable today": fmt_rate(int(g.full_path.sum()), n)})
    write_table("e10b_coverage", pd.DataFrame(agg),
                "E10b: edges buildable for storefronts sampled from the Tranco list (passive measurement)",
                "Storefronts are Tranco 56WKN domains in the market's ccTLDs (US: .com/.us with USD prices) whose "
                "homepage shows a cart or checkout marker and a product marker (or two cart markers and a known "
                "commerce platform), taken in rank order. Storefronts that render entirely in JavaScript are missed, "
                "so the sample leans towards server-rendered shops. One homepage request per site. With no retailer legal name, the LEI "
                "lookup uses the certificate organisation or the domain label, so LEI candidates are looser than in "
                "E10 and need confirmation. Wilson 95% intervals.", index=False)
    return {"coverage": agg, "n": len(df),
            "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def run_e10() -> Dict:
    with open(os.path.join(ROOT, "data", "retailers.yaml")) as fh:
        retailers = yaml.safe_load(fh)
    jobs = [(e, m) for m, lst in retailers["markets"].items() for e in (lst[:5] if QUICK else lst)]
    with Timer(f"E10 measuring {len(jobs)} retailers"):
        with ThreadPoolExecutor(8) as ex:
            rows = list(ex.map(lambda j: measure(*j), jobs))
    df = pd.DataFrame(rows)
    write_csv("e10_retailers", df)
    agg = []
    for m, g in df.groupby("market"):
        n = len(g)
        agg.append({"market": m, "retailers": n,
                    "L0->L1 domain to entity": fmt_rate(int(g.edge_L0_L1.sum()), n),
                    "verified mark (VMC)": fmt_rate(int(g.edge_mark.sum()), n),
                    "LEI issued": fmt_rate(int(g.edge_L1_lei.sum()), n),
                    "platform/PSP identifiable": fmt_rate(int(g.edge_L1_L2L3.sum()), n),
                    "bank terminal binding (VoP/CoP)": "yes" if VOP_POLICY[m][0] else "no",
                    "G1 route buildable (no terminal binding)": fmt_rate(int(g.g1_path.sum()), n),
                    "full path buildable today": fmt_rate(int(g.full_path.sum()), n)})
    write_table("e10_coverage", pd.DataFrame(agg), "E10: receiving-authority edges buildable from public / KYB data",
                "Wilson 95% intervals. 'Identifiable' means the storefront exposes the PSP or commerce platform that "
                "already runs KYB; LEI matches are name-based and need manual confirmation before use. "
                + " ".join(f"{k}: {v[1]}." for k, v in VOP_POLICY.items()), index=False)
    with Timer("E10 lookalike prevalence"):
        k = 8 if QUICK else 25
        with ThreadPoolExecutor(8) as ex:
            looks = list(ex.map(lambda d: lookalikes(d, None, k), df.domain.tolist()))
    lk = pd.DataFrame(looks).merge(df[["domain", "market"]], on="domain")
    write_csv("e10_lookalikes", lk)
    lagg = lk.groupby("market").agg(retailers=("domain", "size"), generated=("generated", "sum"),
                                     registered=("registered", "sum")).reset_index()
    lagg["registered share"] = (lagg.registered / lagg.generated).round(3)
    lagg["retailers with >=1 registered lookalike"] = lk.groupby("market").apply(
        lambda g: f"{int((g.registered > 0).sum())}/{len(g)}").values
    write_table("e10_lookalike_prevalence", lagg, "E10: registered lookalike domains (DNS A or NS record exists)",
                "Registered does not mean malicious: many are defensive registrations by the brand itself.",
                index=False)
    out = {"coverage": agg, "lookalikes": lagg.to_dict(orient="records"), "n": len(df),
           "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    out["sampled"] = run_e10b(20 if QUICK else 250, 400 if QUICK else 4000)
    write_json("e10_summary", out)
    return out


if __name__ == "__main__":
    print(run_e10())
