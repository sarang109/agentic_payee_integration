"""Mechanized verification: runs every Tamarin theory variant and the
ProVerif models, and records each lemma's result next to the expected one
(a lemma expected to fail is a sanity check that the property depends on
the mechanism removed in that variant)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from typing import Dict, List

import pandas as pd

from .common import RAW, ROOT, Timer, write_json, write_table

TAMARIN = shutil.which("tamarin-prover")
PROVERIF = os.environ.get("PROVERIF") or shutil.which("proverif") or os.path.expanduser("~/.local/src/proverif2.05/proverif")
FORMAL = os.path.join(ROOT, "formal")

RUNS = [
    ("meridian_v1.spthy", "", {"executable": "verified", "df_soundness": "verified",
                               "unilateral_claim_resistance": "verified", "post_binding_swap": "verified",
                               "release_unique": "verified"}),
    ("meridian_v1.spthy", "NOBETA", {"post_binding_swap": "falsified"}),
    ("meridian_v1.spthy", "ONESIDED", {"unilateral_claim_resistance": "falsified"}),
    ("meridian_g2.spthy", "", {"executable_g2": "verified", "executable_blame": "verified",
                               "committed_route_soundness": "verified", "commitment_authentic": "verified",
                               "no_false_blame": "verified"}),
    ("checkout_ext.spthy", "", {"executable": "verified", "payee_authenticity": "falsified",
                                "endpoint_compromise_only": "falsified", "discovery_runtime_consistency": "falsified"}),
    ("checkout_ext.spthy", "MERIDIAN", {"executable": "verified", "payee_authenticity": "verified",
                                        "endpoint_compromise_only": "verified",
                                        "discovery_runtime_consistency": "verified"}),
]
PV_RUNS = [("private_lookup.pv", "true"), ("private_lookup_full_hash.pv", "cannot be proved")]


def run_formal() -> Dict:
    rows: List[Dict] = []
    logs = os.path.join(RAW, "formal_logs")
    os.makedirs(logs, exist_ok=True)
    if TAMARIN is None:
        rows.append({"model": "tamarin", "variant": "-", "lemma": "-", "result": "tamarin-prover not installed",
                     "expected": "-", "as expected": False})
    else:
        for fn, flag, expected in RUNS:
            args = [TAMARIN, "--prove"] + ([f"-D={flag}"] if flag else []) + [os.path.join(FORMAL, "tamarin", fn)]
            with Timer(f"tamarin {fn} {flag or 'default'}"):
                t0 = time.perf_counter()
                out = subprocess.run(args, capture_output=True, text=True, timeout=3600).stdout
                secs = time.perf_counter() - t0
            with open(os.path.join(logs, f"{fn}.{flag or 'default'}.txt"), "w") as fh:
                fh.write(out)
            for m in re.finditer(r"^\s+(\w+) \((all-traces|exists-trace)\): (verified|falsified)[^\n]*?\((\d+) steps\)",
                                 out, re.M):
                lemma, _, res, steps = m.groups()
                exp = expected.get(lemma, "")
                rows.append({"model": fn, "variant": flag or "default", "lemma": lemma, "result": res,
                             "steps": int(steps), "expected": exp or "(not asserted)",
                             "as expected": (res == exp) if exp else True, "seconds": round(secs, 2)})
    if not os.path.exists(PROVERIF):
        rows.append({"model": "proverif", "variant": "-", "lemma": "-", "result": "proverif not installed",
                     "expected": "-", "as expected": False})
    else:
        for fn, exp in PV_RUNS:
            with Timer(f"proverif {fn}"):
                out = subprocess.run([PROVERIF, os.path.join(FORMAL, "proverif", fn)], capture_output=True, text=True,
                                     timeout=3600).stdout
            with open(os.path.join(logs, f"{fn}.txt"), "w") as fh:
                fh.write(out)
            m = re.search(r"RESULT Observational equivalence (is true|cannot be proved|is false)", out)
            res = m.group(1).replace("is ", "") if m else "no result"
            rows.append({"model": fn, "variant": "diff-equivalence", "lemma": "observational equivalence",
                         "result": res, "steps": None, "expected": exp, "as expected": res == exp})
    df = pd.DataFrame(rows)
    write_table("formal_results", df, "Mechanized verification (Tamarin 1.12, ProVerif 2.05)",
                "Variants: NOBETA removes the payee binding token, ONESIDED removes operator acceptance, "
                "MERIDIAN adds the extension to the AP2/ACP-style checkout. A lemma expected to be falsified is a "
                "sanity check that the property depends on the removed mechanism.", index=False)
    out = {"all_as_expected": bool(df["as expected"].all()), "n": len(df)}
    write_json("formal_summary", out)
    return out


if __name__ == "__main__":
    print(run_formal())
