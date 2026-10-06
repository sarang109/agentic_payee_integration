"""E4b: anchoring against real phishing domains (UCI PhiUSIIL, CC BY 4.0).

Genuine brands are the Tranco top labels (list 56WKN). Every domain in the
PhiUSIIL dataset is matched to the top brand it most resembles (skeleton
edit similarity of domain labels, or the brand label embedded in a longer
label). Then:

  attack trials   the user names brand B, the agent surfaces a phishing
                  domain that resembles B; does CBA commit to it?
  benign trials   the user names brand B and the registry also contains the
                  legitimate (label 1) domains that resemble B; how often is
                  the user asked to disambiguate?

Phishing domains are real, so the lookalike techniques are whatever
attackers actually used; page titles serve as the semantic description and
no logos are available (visual feature off).
"""

from __future__ import annotations

import hashlib
import os
import random
import re
import urllib.request
import zipfile
from typing import Dict, List, Optional, Tuple

import pandas as pd

from meridian.cba import CBA, Candidate, Registry
from meridian.cba.confusables import fold
from meridian.cba.features import similarity
from meridian.core.ids import make_lei

from .common import QUICK, ROOT, SEED, Timer, write_csv, write_json, write_table
from .e2_e3 import calibrated_cba
from .stats import fmt_rate

URL = "https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip"
SHA256 = "0a639fd03aea6308c5b1c10c92aa23c2ce1505447a9137271865cd0badc9a59a"
ZIP = os.path.join(ROOT, "data", "phishing", "phiusiil.zip")
TRANCO = os.path.join(ROOT, "data", "tranco", "tranco_56WKN_top20k.csv")
HOSTING = {"firebaseapp", "web", "weebly", "weeblysite", "wixsite", "github", "blogspot", "ipfs", "glitch", "netlify",
           "herokuapp", "vercel", "000webhostapp", "duckdns", "ngrok", "pages", "appspot", "azurewebsites", "workers",
           "repl", "square", "godaddysites", "webflow", "yolasite", "sites", "google", "com", "co", "net", "org", "www"}


def fetch() -> str:
    if not os.path.exists(ZIP):
        os.makedirs(os.path.dirname(ZIP), exist_ok=True)
        urllib.request.urlretrieve(URL, ZIP)
    with open(ZIP, "rb") as fh:
        if hashlib.sha256(fh.read()).hexdigest() != SHA256:
            raise RuntimeError("PhiUSIIL archive checksum mismatch")
    return ZIP


def brands(n: int) -> List[Tuple[str, str]]:
    out, seen = [], set()
    with open(TRANCO) as fh:
        for line in fh:
            dom = line.strip().split(",", 1)[1]
            label = dom.split(".")[0]
            if label.isalpha() and 4 <= len(label) <= 12 and label not in seen and label not in HOSTING:
                seen.add(label)
                out.append((label, dom))
            if len(out) >= n:
                break
    return out


def labels(domain: str) -> List[str]:
    d = domain.lower().removeprefix("www.")
    parts = [p for p in re.split(r"[.]", d) if p]
    return [p for p in parts[:-1] if p not in HOSTING] or parts[:1]


def match(domain: str, reg: Registry, brand_by_label: Dict[str, str]) -> Optional[Tuple[str, float, str]]:
    """Best-resembling brand for a domain: (brand label, similarity, how)."""
    best = None
    for lab in labels(domain):
        f = fold(lab)
        for tok in re.split(r"[-_]", f) + [f]:
            if tok in brand_by_label:
                cand = (tok, 1.0, "exact-token" if tok != f else "exact")
                if best is None or cand[1] > best[1]:
                    best = cand
        for b, _ in [(b, 0) for b in brand_by_label if len(b) >= 5 and b in f and b != f]:
            cand = (b, 0.95, "embedded")
            if best is None or cand[1] > best[1]:
                best = cand
        for c in reg.retrieve(f, k=4):
            bl = c.brand_id.split(":", 1)[1].split(".")[0]
            sim = similarity(f, fold(bl))
            if sim >= 0.75 and (best is None or sim > best[1]):
                best = (bl, sim, "edit")
    return best


def trials(name: str, df: pd.DataFrame, top: List[Tuple[str, str]], n_attack: int, rng: random.Random) -> Dict:
    """Anchoring trials for one dataset. ``df`` has columns domain, title,
    phishing (bool). Returns the summary rows and the match table."""
    genuine = [Candidate(f"brand:{dom}", lab.capitalize(), dom, make_lei(f"tranco|{dom}"), None,
                         f"{lab} official website", 0, "") for lab, dom in top]
    reg = Registry(genuine)
    brand_by_label = {lab: dom for lab, dom in top}
    top_domains = {dom for _, dom in top} | {f"www.{dom}" for _, dom in top}
    rows = []
    for dom, title, ph in df[["domain", "title", "phishing"]].itertuples(index=False):
        if not isinstance(dom, str) or dom in top_domains:
            continue
        m = match(dom, reg, brand_by_label)
        if m:
            rows.append({"dataset": name, "domain": dom, "title": str(title)[:120], "phishing": bool(ph),
                         "brand": m[0], "similarity": round(m[1], 3), "how": m[2]})
    mt = pd.DataFrame(rows, columns=["dataset", "domain", "title", "phishing", "brand", "similarity", "how"])
    params = calibrated_cba()
    cba_g = CBA(reg, params)
    phish = mt[mt.phishing]
    sample_p = phish.sample(min(len(phish), n_attack), random_state=SEED) if len(phish) else phish
    att = []
    for r in sample_p.itertuples():
        b = r.brand
        lk = Candidate(f"brand:{r.domain}", r.domain.removeprefix("www.").split(".")[0].capitalize(), r.domain,
                       make_lei(f"phish|{r.domain}"), None, r.title, 0, "")
        words = b if rng.random() < 0.6 else b.capitalize()
        a = cba_g.anchor(words, [lk])
        att.append({"how": r.how, "committed_to_phish": a.committed and a.brand == lk.brand_id,
                    "committed_to_brand": a.committed and a.brand == f"brand:{brand_by_label[b]}",
                    "step_up": not a.committed})
    at = pd.DataFrame(att, columns=["how", "committed_to_phish", "committed_to_brand", "step_up"])
    legit = mt[~mt.phishing]
    res = [{"dataset": name, "trial": "attack: agent surfaces a real phishing domain resembling the named brand",
            "n": len(at), "committed to phishing domain": fmt_rate(int(at.committed_to_phish.sum()), len(at)),
            "committed to genuine brand": fmt_rate(int(at.committed_to_brand.sum()), len(at)),
            "stepped up": fmt_rate(int(at.step_up.sum()), len(at))}]
    if len(legit):
        reg_b = Registry(genuine)
        for r in legit.itertuples():
            reg_b.add(Candidate(f"brand:{r.domain}", r.domain.removeprefix("www.").split(".")[0].capitalize(),
                                r.domain, make_lei(f"legit|{r.domain}"), None, r.title, 0, ""))
        cba_b = CBA(reg_b, params)
        ben = []
        for lab, dom in top:
            a = cba_b.anchor(lab if rng.random() < 0.6 else lab.capitalize(), [])
            ben.append({"step_up": not a.committed, "wrong": a.committed and a.brand != f"brand:{dom}"})
        bt = pd.DataFrame(ben)
        res.append({"dataset": name, "trial": "benign: registry also holds this dataset's legitimate look-alike domains",
                    "n": len(bt), "committed to phishing domain": "-",
                    "committed to genuine brand": fmt_rate(int((~bt.step_up & ~bt.wrong).sum()), len(bt)),
                    "stepped up": fmt_rate(int(bt.step_up.sum()), len(bt))})
    cov = {"dataset": name, "domains": int(df.domain.nunique()), "phishing": int(df.phishing.sum()),
           "phishing resembling a top brand": int(len(phish)), "legitimate resembling a top brand": int(len(legit))}
    by = at.groupby("how").agg(n=("step_up", "size"), committed_to_phish=("committed_to_phish", "sum"),
                               step_up=("step_up", "mean")).reset_index()
    by.insert(0, "dataset", name)
    return {"res": res, "cov": cov, "by": by, "matches": mt}


def run_e4b() -> Dict:
    fetch()
    n_brands = 600 if QUICK else 2000
    with Timer("E4b load PhiUSIIL"):
        df = pd.read_csv(zipfile.ZipFile(ZIP).open("PhiUSIIL_Phishing_URL_Dataset.csv"),
                         usecols=["Domain", "Title", "label"]).drop_duplicates("Domain")
    if QUICK:
        df = df.sample(30_000, random_state=SEED)
    df = pd.DataFrame({"domain": df.Domain, "title": df.Title, "phishing": df.label == 0})
    top = brands(n_brands)
    with Timer(f"E4b trials on {len(df)} PhiUSIIL domains"):
        out = trials("UCI PhiUSIIL", df, top, 600 if QUICK else 4000, random.Random(SEED))
    write_csv("e4b_matches", out["matches"])
    params = calibrated_cba()
    write_table("e4b_phishing", pd.DataFrame(out["res"]).drop(columns=["dataset"]),
                f"E4b: anchoring against real phishing domains (PhiUSIIL; {len(top)} Tranco brands; "
                f"theta={params.theta}, tau={params.tau})",
                "Wilson 95% intervals. Visual feature off (no logos); titles as descriptions.", index=False)
    write_table("e4b_by_match", out["by"].drop(columns=["dataset"]).round(3),
                "E4b: attack trials by how the phishing domain resembles the brand", index=False)
    write_table("e4b_coverage", pd.DataFrame([out["cov"]]).drop(columns=["dataset"]),
                "E4b: how many dataset domains resemble a Tranco top brand", index=False)
    summary = {"attack": out["res"][0], "benign": out["res"][1] if len(out["res"]) > 1 else None,
               "coverage": out["cov"]}
    write_json("e4b_summary", summary)
    return summary


if __name__ == "__main__":
    print(run_e4b())
