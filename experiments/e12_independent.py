"""E12: independently authored attack set (Gate A of the publication plan).

    python -m experiments.e12_independent validate [e12/attacks.json]
    python -m experiments.e12_independent freeze   [e12/attacks.json]
    python -m experiments.e12_independent run

``validate`` checks the schema and compiles every attack on a fresh world. It
uses ground truth only (does the money reach a wrong terminal if every check
allows it?) and never evaluates a configuration, so an attack cannot be tuned
against a result.

``freeze`` writes ``e12/LOCK`` with the SHA-256 of the attack file and of
``e12/DECISION_RULE.md``. It needs at least 30 attacks, at least two distinct
authors and the decision rule already in the tree; it refuses to overwrite an
existing lock.

``run`` refuses unless both files match the lock, runs B1-B7 and the MERIDIAN
configurations on the frozen attacks, applies the decision rule and appends to
``e12/RUN_LOG.jsonl``. The result is reported whatever it shows. A later run
must reproduce the first one exactly; the log records whether it does.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

import pandas as pd

from payeebench.configs import ALL_CONFIGS
from payeebench.e12 import compile_attacks, diverts_if_paid, validate_file
from payeebench.runner import run
from payeebench.world import World

from .common import ROOT, Timer, write_csv, write_json, write_table
from .e2_e3 import calibrated_cba
from .stats import mcnemar_exact

E12_DIR = os.path.join(ROOT, "e12")
ATTACKS = os.path.join(E12_DIR, "attacks.json")
RULE = os.path.join(E12_DIR, "DECISION_RULE.md")
LOCK = os.path.join(E12_DIR, "LOCK")
RUN_LOG = os.path.join(E12_DIR, "RUN_LOG.jsonl")

E12_SEED = 12012
MIN_ATTACKS = 30
MIN_AUTHORS = 2
PRIMARY = ("M2", "B7")
ALPHA = 0.05
CONFIGS = [c for c in ALL_CONFIGS]  # B1-B7 and M1-G1, M1, M2, M3; M1 and M2 are the pre-declared ones


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_attacks(path: str | None = None) -> Dict[str, Any]:
    with open(path or ATTACKS, encoding="utf-8") as fh:
        return json.load(fh)


def _git() -> str:
    try:
        return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "uncommitted"


def _compile(doc: Dict[str, Any]):
    world = World(seed=E12_SEED).build()
    cases = compile_attacks(world, doc["attacks"], seed=E12_SEED)
    return world, cases


def validate(path: str | None = None, min_attacks: int = 0, min_authors: int = 0) -> List[str]:
    path = path or ATTACKS
    if not os.path.exists(path):
        return [f"{os.path.relpath(path, ROOT)} does not exist"]
    doc = load_attacks(path)
    problems = validate_file(doc, min_attacks, min_authors)
    if problems:
        return problems
    world, cases = _compile(doc)
    for c in cases:
        if not diverts_if_paid(world, c):
            problems.append(f"{c.case_id}: as compiled, the money reaches a legitimate terminal even if every check "
                            f"allows it, so this is not an attack; change it or remove it before the freeze")
    return problems


def freeze(path: str | None = None) -> int:
    path = path or ATTACKS
    if os.path.exists(LOCK):
        print("e12/LOCK already exists; a frozen set is never edited or re-frozen.")
        return 1
    if not os.path.exists(RULE):
        print("e12/DECISION_RULE.md must exist before the freeze.")
        return 1
    problems = validate(path, MIN_ATTACKS, MIN_AUTHORS)
    if problems:
        print("not frozen:")
        for p in problems:
            print("  -", p)
        return 1
    doc = load_attacks(path)
    lock = {"schema": doc["schema"], "attacks_sha256": sha256_file(path), "decision_rule_sha256": sha256_file(RULE),
            "attacks": len(doc["attacks"]), "authors": sorted({a["author"] for a in doc["attacks"]}),
            "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git": _git()}
    with open(LOCK, "w") as fh:
        json.dump(lock, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"frozen {lock['attacks']} attacks by {len(lock['authors'])} authors: {lock['attacks_sha256']}")
    return 0


def lock_status() -> Dict[str, Any]:
    st: Dict[str, Any] = {"ok": False, "reason": ""}
    if not os.path.exists(LOCK):
        st["reason"] = "e12/LOCK does not exist: the attack set is not frozen"
        return st
    with open(LOCK) as fh:
        lock = json.load(fh)
    st["lock"] = lock
    if not (os.path.exists(ATTACKS) and sha256_file(ATTACKS) == lock["attacks_sha256"]):
        st["reason"] = "e12/attacks.json changed after the freeze"
    elif not (os.path.exists(RULE) and sha256_file(RULE) == lock["decision_rule_sha256"]):
        st["reason"] = "e12/DECISION_RULE.md changed after the freeze"
    else:
        st["ok"] = True
    return st


# ------------------------------------------------------------------ analysis

def decide(df: pd.DataFrame) -> Dict[str, Any]:
    """The pre-declared decision (e12/DECISION_RULE.md): M2 against B7 on the
    in-model attacks, exact McNemar."""
    a, b = PRIMARY
    inm = df[~df.premise_violation]
    la = inm[inm.config == a].set_index("case_id").loss
    lb = inm[inm.config == b].set_index("case_id").loss
    lb = lb.reindex(la.index)
    a_only = int((la & ~lb).sum())
    b_only = int((~la & lb).sum())
    p = mcnemar_exact(a_only, b_only)
    n = int(len(la))
    if a_only > b_only:
        label = "advantage-reversed"
    elif b_only > a_only and p < ALPHA:
        label = "advantage-holds"
    else:
        label = "advantage-not-significant"
    return {"comparison": f"{a} vs {b}", "attacks_in_model": n, f"{a}_losses": int(la.sum()),
            f"{b}_losses": int(lb.sum()), f"loss_only_under_{a}": a_only, f"loss_only_under_{b}": b_only,
            "p_exact_mcnemar": p, "alpha": ALPHA, "label": label,
            "wording": {"advantage-holds": "outperforms language is permitted for M2 against B7 on this set",
                        "advantage-not-significant": "report the shrunken result; no outperforms language",
                        "advantage-reversed": "report the reversal; no outperforms language; reframe the paper "
                                              "around the framework and the X2/X3 findings"}[label]}


def run_e12() -> dict:
    st = lock_status()
    if not st["ok"]:
        return {"status": f"skipped: {st['reason']}"}
    doc = load_attacks()
    with Timer("E12 compile frozen attacks"):
        world, cases = _compile(doc)
    invalid = [c.case_id for c in cases if not diverts_if_paid(world, c)]
    if invalid:
        raise RuntimeError(f"frozen attacks that do not divert even if allowed: {invalid}")
    with Timer("E12 run configurations"):
        recs = run(world, cases, CONFIGS, delta=world.delta, cba_params=calibrated_cba(), seed=E12_SEED)
    df = pd.DataFrame(recs)
    meta = {a["id"]: a for a in doc["attacks"]}
    df["author"] = df.case_id.map(lambda c: meta[c]["author"])
    df["scenario"] = df.case_id.map(lambda c: meta[c]["scenario"]["kind"])
    write_csv("e12_records", df)

    n_all = df.case_id.nunique()
    inm = df[~df.premise_violation]
    order = [c for c in CONFIGS]
    rows = []
    for scope, d in (("in-model", inm), ("premise-violation", df[df.premise_violation])):
        for kind, g in [("all", d)] + sorted(d.groupby("scenario")):
            for cfg in order:
                x = g[g.config == cfg]
                rows.append({"set": scope, "scenario": kind, "config": cfg, "attacks": len(x),
                             "loss": int(x.loss.sum()), "step-up": int(x.step_up.sum()),
                             "denied": int((x.verdict == "DENY").sum())})
    long = pd.DataFrame(rows)
    mat = long[long.scenario == "all"].pivot(index="set", columns="config", values="loss")[order]
    cnt = long[long.scenario == "all"].groupby("set").attacks.first()
    mat = mat.astype(int).astype(str).apply(lambda col: col + "/" + cnt.reindex(mat.index).astype(int).astype(str))
    write_table("e12_attack_matrix", mat, "E12: losses on the independently authored attacks",
                "Exact counts of attacks whose money reached an illegitimate terminal and was not undone. The "
                "attack set was frozen (e12/LOCK) before this run and is the same for every configuration.")
    by = long[(long.set == "in-model") & (long.scenario != "all")].pivot(index="scenario", columns="config",
                                                                        values="loss")[order]
    write_table("e12_by_scenario", by, "E12: losses by scenario kind (in-model)",
                "Exploratory; small counts per kind.")
    write_csv("e12_long", long)

    dec = decide(df)
    pairs = []
    for x, y in [("M2", "B7"), ("M1", "B7"), ("M2", "M1"), ("M3", "M2"), ("M1", "M1-G1"), ("M3", "B7")]:
        lx = inm[inm.config == x].set_index("case_id").loss
        ly = inm[inm.config == y].set_index("case_id").loss.reindex(lx.index)
        xo, yo = int((lx & ~ly).sum()), int((~lx & ly).sum())
        pairs.append({"A": x, "B": y, "loss only under A": xo, "loss only under B": yo,
                      "p (exact McNemar)": mcnemar_exact(xo, yo),
                      "role": "pre-declared primary" if (x, y) == PRIMARY else "exploratory"})
    write_table("e12_mcnemar", pd.DataFrame(pairs), "E12: paired exact McNemar tests (in-model)",
                "Only the first row is the pre-declared confirmatory test (e12/DECISION_RULE.md); the others are "
                "exploratory and are not corrected for multiple comparisons.", index=False)

    ba = inm[inm.config.isin(["M2", "B7"])].pivot_table(index=["author", "case_id"], columns="config", values="loss",
                                                       aggfunc="first").reset_index()
    ba_rows = []
    for au, g in ba.groupby("author"):
        ba_rows.append({"author": au, "attacks": len(g), "M2 losses": int(g.M2.sum()), "B7 losses": int(g.B7.sum()),
                        "only M2": int((g.M2 & ~g.B7).sum()), "only B7": int((~g.M2 & g.B7).sum())})
    write_table("e12_by_author", pd.DataFrame(ba_rows), "E12: M2 against B7 by author (in-model)",
                "Shows whether the result depends on one author's attacks.", index=False)

    summary = {"decision": dec, "attacks": n_all, "in_model": int(inm.case_id.nunique()),
               "premise_violation": int(n_all - inm.case_id.nunique()), "lock": st["lock"], "seed": E12_SEED,
               "authors": st["lock"]["authors"]}
    first = None
    if os.path.exists(RUN_LOG):
        with open(RUN_LOG) as fh:
            lines = [json.loads(x) for x in fh if x.strip()]
        first = lines[0] if lines else None
    digest = hashlib.sha256(json.dumps({k: summary[k] for k in ("decision", "attacks", "in_model")},
                                       sort_keys=True).encode()).hexdigest()
    summary["result_sha256"] = digest
    summary["matches_first_run"] = True if first is None else first["result_sha256"] == digest
    with open(RUN_LOG, "a") as fh:
        fh.write(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git": _git(),
                             "attacks_sha256": st["lock"]["attacks_sha256"], "result_sha256": digest,
                             "label": dec["label"]}, sort_keys=True) + "\n")
    write_json("e12_summary", summary)
    return summary


def main(argv: List[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "validate"
    path = argv[2] if len(argv) > 2 else None
    if cmd == "validate":
        problems = validate(path)
        for p in problems:
            print("-", p)
        print("valid" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    if cmd == "freeze":
        return freeze(path)
    if cmd == "run":
        print(json.dumps(run_e12(), indent=2, default=str))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
