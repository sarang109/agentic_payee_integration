"""E4c: anchoring on Kaggle phishing datasets.

(a) Adversarial Homograph Detection (alishan07, CC BY-SA 4.0): every spoof
    names the domain it imitates and its attack type (IDN Cyrillic / Greek /
    mixed script, zero-width, BiDi override, fullwidth syntax, ASCII
    homoglyphs, punycode, ...). For each spoof: is it flagged as a
    confusable rival of its target (kappa >= theta), and when the user names
    the target while the agent surfaces the spoof, does CBA commit to it?
    Benign rows give the false-rival rate between unrelated domains.
(b) URL datasets (malicious URLs by sid321axn, phishing site URLs by
    taruntiwarihp, PhishTank 2026 by quangnguynv): the E4b procedure, with
    each dataset's benign rows as the control where it has them.

Needs a Kaggle API token (~/.kaggle/access_token or KAGGLE_API_TOKEN);
without it the step records that it was skipped. Files are downloaded to
data/kaggle/ (not tracked) and their SHA-256 is written to the results.
"""

from __future__ import annotations

import hashlib
import os
import random
import shutil
import subprocess
import sys
import unicodedata
import urllib.parse
from typing import Dict, List, Optional

import pandas as pd

from meridian.cba import CBA, Candidate, Registry
from meridian.core.ids import make_lei

from .common import QUICK, ROOT, SEED, Timer, write_csv, write_json, write_table
from .e2_e3 import calibrated_cba
from .e4b_phishing import brands, trials
from .stats import fmt_rate

KAGGLE = os.path.join(ROOT, "data", "kaggle")
DATASETS = {
    "homograph": ("alishan07/adversarial-homograph-detection",
                  "adversarial-homograph-detection/adversarial-homograph-detection/homograph_phishing_test.csv"),
    "malicious_urls": ("sid321axn/malicious-urls-dataset", "malicious-urls-dataset/malicious_phish.csv"),
    "phishing_site_urls": ("taruntiwarihp/phishing-site-urls", "phishing-site-urls/phishing_site_urls.csv"),
    "phishtank_2026": ("quangnguynv/phishtank-phishingurl-valid-dataset",
                       "phishtank-phishingurl-valid-dataset/PhishTank_2026.csv"),
}


def have_token() -> bool:
    return bool(os.environ.get("KAGGLE_API_TOKEN")) or os.path.exists(os.path.expanduser("~/.kaggle/access_token")) \
        or os.path.exists(os.path.expanduser("~/.kaggle/kaggle.json"))


def fetch(key: str) -> Optional[str]:
    ref, rel = DATASETS[key]
    path = os.path.join(KAGGLE, rel)
    if os.path.exists(path):
        return path
    if not have_token():
        return None
    exe = shutil.which("kaggle") or os.path.join(os.path.dirname(sys.executable), "kaggle")
    dest = os.path.join(KAGGLE, ref.split("/")[1])
    subprocess.run([exe, "datasets", "download", "-d", ref, "-p", dest, "--unzip", "-q"], check=True,
                   capture_output=True)
    return path if os.path.exists(path) else None


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def host(url: str) -> Optional[str]:
    u = url.strip()
    if "://" not in u:
        u = "http://" + u
    try:
        h = urllib.parse.urlsplit(u).hostname
    except ValueError:
        return None
    if not h or h.replace(".", "").isdigit():
        return None
    return h.lower()


def displayed(domain: str) -> str:
    """What a user is shown: punycode labels rendered as Unicode."""
    out = []
    for lab in domain.split("."):
        if lab.startswith("xn--"):
            try:
                lab = lab.encode("ascii").decode("idna")
            except Exception:
                pass
        out.append(lab)
    return ".".join(out)


def first_label(domain: str) -> str:
    d = domain.lower()
    for p in ("www.", "www．"):
        d = d.removeprefix(p)
    return unicodedata.normalize("NFC", d).split(".")[0].split("．")[0]


def homograph(top) -> pd.DataFrame:
    path = fetch("homograph")
    df = pd.read_csv(path)
    if QUICK:
        df = df.sample(4000, random_state=SEED)
    params = calibrated_cba()
    background = [Candidate(f"brand:{dom}", lab.capitalize(), dom, make_lei(f"tranco|{dom}"), None,
                            f"{lab} website", 0, "") for lab, dom in top]
    cba = CBA(Registry(background), params)
    rng = random.Random(SEED)
    rows = []
    benign = df[df.label == 0].url.astype(str).tolist()
    for r in df.itertuples():
        url = str(r.url)
        if r.label == 1:
            src = str(r.source_domain)
            g = Candidate(f"brand:{src}", first_label(src).capitalize(), src, make_lei(f"src|{src}"), None,
                          f"{first_label(src)} website", 0, "")
            disp = displayed(url)
            s = Candidate(f"brand:spoof|{url}", first_label(disp), disp, make_lei(f"spoof|{url}"), None,
                          f"{first_label(src)} website", 0, "")
            cba.registry.add(g)
            kap = cba.kappa(g, s)
            a = cba.anchor(first_label(src), [g, s])
            rows.append({"attack_type": r.attack_type, "subtype": r.attack_subtype, "kappa": kap,
                         "flagged_rival": kap >= params.theta,
                         "committed_to_spoof": a.committed and a.brand == s.brand_id,
                         "committed_to_genuine": a.committed and a.brand == g.brand_id,
                         "step_up": not a.committed})
        else:
            other = rng.choice(benign)
            if other == url:
                continue
            x = Candidate(f"brand:{url}", first_label(url).capitalize(), url, "L1", None, f"{first_label(url)} website")
            y = Candidate(f"brand:{other}", first_label(other).capitalize(), other, "L2", None,
                          f"{first_label(other)} website")
            kap = cba.kappa(x, y)
            rows.append({"attack_type": "benign pair", "subtype": "benign", "kappa": kap,
                         "flagged_rival": kap >= params.theta, "committed_to_spoof": False,
                         "committed_to_genuine": False, "step_up": False})
    return pd.DataFrame(rows)


def url_dataset(key: str) -> Optional[pd.DataFrame]:
    path = fetch(key)
    if path is None:
        return None
    df = pd.read_csv(path)
    if key == "malicious_urls":
        df = df[df.type.isin(["phishing", "benign"])]
        out = pd.DataFrame({"url": df.url, "phishing": df.type == "phishing"})
    elif key == "phishing_site_urls":
        out = pd.DataFrame({"url": df.URL, "phishing": df.Label == "bad"})
    else:
        out = pd.DataFrame({"url": df.URL, "phishing": df.Label == 1})
    out["domain"] = out.url.astype(str).map(host)
    out = out.dropna(subset=["domain"]).drop_duplicates("domain")
    out["title"] = ""
    if QUICK:
        out = out.sample(min(len(out), 30_000), random_state=SEED)
    return out[["domain", "title", "phishing"]]


def run_e4c() -> Dict:
    if not have_token() and not all(os.path.exists(os.path.join(KAGGLE, rel)) for _, rel in DATASETS.values()):
        out = {"status": "skipped: no Kaggle API token"}
        write_json("e4c_summary", out)
        return out
    top = brands(600 if QUICK else 2000)
    params = calibrated_cba()
    files = []
    with Timer("E4c homograph dataset"):
        h = homograph(top)
    write_csv("e4c_homograph_rows", h)
    agg = []
    for t, g in h.groupby("attack_type"):
        n = len(g)
        row = {"attack type": t, "n": n, "flagged as rival (kappa >= theta)": fmt_rate(int(g.flagged_rival.sum()), n)}
        if t != "benign pair":
            row.update({"committed to spoof": fmt_rate(int(g.committed_to_spoof.sum()), n),
                        "committed to genuine": fmt_rate(int(g.committed_to_genuine.sum()), n),
                        "stepped up": fmt_rate(int(g.step_up.sum()), n)})
        agg.append(row)
    att = h[h.attack_type != "benign pair"]
    agg.append({"attack type": "ALL ATTACKS", "n": len(att),
                "flagged as rival (kappa >= theta)": fmt_rate(int(att.flagged_rival.sum()), len(att)),
                "committed to spoof": fmt_rate(int(att.committed_to_spoof.sum()), len(att)),
                "committed to genuine": fmt_rate(int(att.committed_to_genuine.sum()), len(att)),
                "stepped up": fmt_rate(int(att.step_up.sum()), len(att))})
    write_table("e4c_homograph", pd.DataFrame(agg).fillna("-"),
                f"E4c: homograph spoofs (Kaggle alishan07 test split; theta={params.theta}, tau={params.tau})",
                "The user names the spoofed brand; the agent surfaces the spoof. Benign pairs are two unrelated "
                "safe domains (false-rival rate). Wilson 95% intervals.", index=False)
    files.append({"dataset": DATASETS["homograph"][0], "file": DATASETS["homograph"][1],
                  "sha256": sha256(os.path.join(KAGGLE, DATASETS["homograph"][1]))})

    res, cov, by = [], [], []
    rng = random.Random(SEED)
    for key in ("malicious_urls", "phishing_site_urls", "phishtank_2026"):
        with Timer(f"E4c {key}"):
            df = url_dataset(key)
            if df is None:
                continue
            out = trials(DATASETS[key][0], df, top, 600 if QUICK else 4000, rng)
        res += out["res"]
        cov.append(out["cov"])
        by.append(out["by"])
        files.append({"dataset": DATASETS[key][0], "file": DATASETS[key][1],
                      "sha256": sha256(os.path.join(KAGGLE, DATASETS[key][1]))})
    write_table("e4c_url_datasets", pd.DataFrame(res), "E4c: anchoring against real phishing domains from Kaggle "
                "URL datasets", "Same procedure as E4b; no page titles in these datasets. Wilson 95% intervals.",
                index=False)
    write_table("e4c_coverage", pd.DataFrame(cov), "E4c: dataset domains resembling a Tranco top brand", index=False)
    if by:
        write_table("e4c_by_match", pd.concat(by).round(3), "E4c: attack trials by how the domain resembles the brand",
                    index=False)
    write_table("e4c_files", pd.DataFrame(files), "E4c: Kaggle files used", index=False)
    summary = {"status": "ok", "homograph_all": agg[-1], "url_datasets": res, "files": files}
    write_json("e4c_summary", summary)
    return summary


if __name__ == "__main__":
    print(run_e4c())
