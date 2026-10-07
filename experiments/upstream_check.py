"""Gate A2: run baseline B2 against upstream reference code.

B2 (mandate payee binding) is specified from AP2 v0.2. The AP2 SDK at the
pinned commit (data/upstream/PINS.txt) has a payee check: `check_payment_
constraints` in `ap2/sdk/constraints.py`, which matches merchants by id when
both sides have one and otherwise by name and website. This step runs that
code, not a copy of it, on PayeeBench cases and reports where it and the
in-repo B2 agree.

Mapping used (stated, not discovered): the user signs an open mandate whose
allowed payee is the merchant as it was at signing. For a case where the payee
was swapped after the mandate, that is the genuine route's payee; otherwise it
is the payee the checkout presents. The in-repo B2 denies exactly the swapped
cases. The groups below vary what the mandate carries (merchant ids present,
or empty with display fields copied or different) because that is where the
upstream rule and B2 can differ.

B5 (EPC Verification of Payee) has no reference implementation: the scheme
rulebook specifies messages and response codes and each payment service
provider implements the name matching. B5 stays re-specified and the report
says so.

The checkout of the pinned commit is fetched into data/upstream/src/AP2
(git-ignored) or taken from MERIDIAN_AP2_SRC. Without it, or without network,
the step is skipped and says why.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, List, Optional

import pandas as pd

from payeebench.cases import GENERATORS
from payeebench.runner import build_bench

from .common import ROOT, Timer, write_csv, write_json, write_table

PINS = os.path.join(ROOT, "data", "upstream", "PINS.txt")
DEFAULT_SRC = os.path.join(ROOT, "data", "upstream", "src", "AP2")
REPO_URL = "https://github.com/google-agentic-commerce/AP2"


def pinned_sha() -> str:
    with open(PINS) as fh:
        for line in fh:
            if line.startswith("AP2 "):
                return line.split("@", 1)[1].strip()
    raise RuntimeError("AP2 is not pinned in data/upstream/PINS.txt")


def ensure_checkout() -> Optional[str]:
    src = os.environ.get("MERIDIAN_AP2_SRC") or DEFAULT_SRC
    want = pinned_sha()

    def head(p: str) -> Optional[str]:
        try:
            return subprocess.check_output(["git", "-C", p, "rev-parse", "HEAD"], text=True,
                                           stderr=subprocess.DEVNULL).strip()
        except Exception:
            return None

    if head(src) == want:
        return src
    if os.environ.get("MERIDIAN_AP2_SRC"):
        return None  # an explicit path that is not at the pinned commit is not used
    try:
        os.makedirs(src, exist_ok=True)
        run = lambda *a: subprocess.run(["git", "-C", src, *a], check=True, capture_output=True, timeout=300)
        if head(src) is None:
            run("init", "-q")
            run("remote", "add", "origin", REPO_URL)
        run("fetch", "-q", "--depth", "1", "origin", want)
        run("checkout", "-q", "FETCH_HEAD")
    except Exception:
        return None
    return src if head(src) == want else None


def _load_upstream(src: str):
    sdk = os.path.join(src, "code", "sdk", "python")
    if sdk not in sys.path:
        sys.path.insert(0, sdk)
    from ap2.sdk.constraints import check_payment_constraints, merchant_matches  # noqa: WPS433 (upstream code)
    from ap2.sdk.generated.open_payment_mandate import AllowedPayees, OpenPaymentMandate
    from ap2.sdk.generated.payment_mandate import PaymentMandate
    from ap2.sdk.generated.types.amount import Amount
    from ap2.sdk.generated.types.merchant import Merchant
    from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
    return dict(check=check_payment_constraints, matches=merchant_matches, AllowedPayees=AllowedPayees,
                Open=OpenPaymentMandate, Closed=PaymentMandate, Amount=Amount, Merchant=Merchant,
                Instrument=PaymentInstrument)


def _violations(u: dict, allowed, closed) -> List[str]:
    openm = u["Open"](constraints=[u["AllowedPayees"](allowed=[allowed])], cnf={})
    closedm = u["Closed"](transaction_id="tx", payee=closed, payment_amount=u["Amount"](amount=1, currency="USD"),
                          payment_instrument=u["Instrument"](id="i", type="card"))
    return u["check"](openm, closedm)


def _reference_payee_check_from_the_paper(allowed_id: str, presented_id: str) -> bool:
    """The behaviour arXiv 2609.00060 reports for an earlier AP2 reference
    (an allowed payee with an empty merchant id matched any payee), as kept in
    meridian.protocols.ap2.reference_allowed_payee_check."""
    from meridian.protocols.ap2 import AllowedPayees, Merchant, reference_allowed_payee_check
    return reference_allowed_payee_check(AllowedPayees([Merchant(allowed_id, "x")]), Merchant(presented_id, "y"))


def run_upstream_check() -> dict:
    src = ensure_checkout()
    if src is None:
        return {"status": "skipped: the AP2 checkout at the pinned commit is not available (no network, or "
                          "MERIDIAN_AP2_SRC is not at the pinned commit); B2 stays re-specified"}
    u = _load_upstream(src)
    M = u["Merchant"]
    with Timer("upstream check: build cases"):
        world, cases = build_bench(seed=7, n_attack=60, n_benign=90, n_pv=0, attacks=tuple(GENERATORS), pvs=())
    rows: List[Dict] = []
    wild: List[Dict] = []
    for c in cases:
        presented = c.payment.payee
        genuine = c.template.payee if c.template is not None else presented
        swapped = bool(c.swap_after_mandate) and genuine != presented
        signed = genuine if swapped else presented
        gname = (c.template.merchant_name if c.template is not None else c.vop_name) or "merchant"
        gsite = world.brands[c.intended].domain
        pname, psite = (c.vop_name or "merchant", c.listing.domain) if swapped else (gname, gsite)
        b2_deny = bool(c.swap_after_mandate)
        # G1: merchant ids present on both sides
        v1 = _violations(u, M(id=signed, name=gname, website=gsite), M(id=presented, name=pname, website=psite))
        rows.append({"group": "G1 ids present", "case": c.case_id, "swapped": swapped, "b2_deny": b2_deny,
                     "upstream_violation": bool(v1)})
        if swapped:
            # G2: no ids in the mandate; the attacker copies the genuine display fields
            v2 = _violations(u, M(id="", name=gname, website=gsite), M(id="", name=gname, website=gsite))
            rows.append({"group": "G2 ids empty, display fields copied", "case": c.case_id, "swapped": True,
                         "b2_deny": True, "upstream_violation": bool(v2)})
            # G3: no ids in the mandate; the attacker's display fields differ
            v3 = _violations(u, M(id="", name=gname, website=gsite), M(id="", name=pname, website=psite))
            rows.append({"group": "G3 ids empty, display fields differ", "case": c.case_id, "swapped": True,
                         "b2_deny": True, "upstream_violation": bool(v3)})
            # G4 (separate table): the empty-id wildcard reported for an earlier reference
            wild.append({"case": c.case_id,
                         "earlier reference accepts": _reference_payee_check_from_the_paper("", presented),
                         "this pin accepts": not _violations(u, M(id="", name=gname, website=gsite),
                                                             M(id=presented, name=pname, website=psite))})
    df = pd.DataFrame(rows)
    write_csv("upstream_b2_rows", df)
    out = []
    for g, d in df.groupby("group"):
        out.append({"group": g, "cases": len(d), "B2 denies": int(d.b2_deny.sum()),
                    "upstream reports a violation": int(d.upstream_violation.sum()),
                    "agree": int((d.b2_deny == d.upstream_violation).sum()),
                    "B2 stricter": int((d.b2_deny & ~d.upstream_violation).sum()),
                    "upstream stricter": int((~d.b2_deny & d.upstream_violation).sum())})
    tab = pd.DataFrame(out)
    write_table("upstream_b2_agreement", tab,
                f"Gate A2: in-repo B2 against the AP2 SDK payee check (upstream commit {pinned_sha()[:12]})",
                "Upstream code was run, not copied. G1 is the mapping documented in experiments/upstream_check.py. In "
                "G2-G4 the mandate carries no merchant id, so the upstream rule falls back to name and website; "
                "'B2 stricter' counts cases where B2 denies and the SDK accepts. No upstream reference code exists "
                "for B5 (EPC Verification of Payee): the rulebook specifies messages and codes, not the matching; "
                "B5 stays re-specified.", index=False)
    wd = pd.DataFrame(wild)
    wtab = pd.DataFrame([{"swapped cases": len(wd), "earlier reference accepts": int(wd["earlier reference accepts"].sum()),
                          "this pin accepts": int(wd["this pin accepts"].sum())}])
    write_table("upstream_empty_id_wildcard", wtab,
                "Gate A2: an allowed payee with an empty merchant id, presented a different payee",
                "The earlier AP2 reference reported in arXiv 2609.00060 matched any payee here; the pinned SDK is "
                "run, the earlier behaviour is the one kept in meridian.protocols.ap2.reference_allowed_payee_check.",
                index=False)
    summary = {"upstream_commit": pinned_sha(), "groups": out, "empty_id_wildcard": wtab.to_dict(orient="records")[0],
               "B5": "no reference implementation; re-specified", "B5": "no reference implementation; re-specified",
               "g1_all_agree": bool((tab.loc[tab.group.str.startswith("G1"), "agree"] ==
                                     tab.loc[tab.group.str.startswith("G1"), "cases"]).all())}
    write_json("upstream_check_summary", summary)
    return summary


if __name__ == "__main__":
    print(run_upstream_check())
