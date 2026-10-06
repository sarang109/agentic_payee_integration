"""ACP checkout (spec 2026-04-17, pinned) with a MERIDIAN extension.

The seller declares the extension in capabilities.extensions and adds
``receiving_authority`` to the checkout session. Before calling
delegate_payment, the credential provider verifies the route and mints an
allowance whose merchant_id is exactly the verified payee p (Shared Payment
Tokens are already merchant-scoped; MERIDIAN decides which scope to mint).
"""

from __future__ import annotations

import copy
import datetime as dt
from typing import List, Optional, Tuple

from ..core.decision import ALLOW, DENY, STEP_UP, Decision, Payment
from ..core.policy import Policy, TrustStore
from ..core.routes import RouteBundle, verify_route
from .ap2 import route_digest

EXTENSION_NAME = "meridian.receiving_authority@2026-10-01"


def checkout_session(session_id: str, payment: Payment, seller_name: str, psp: str, bundle: Optional[RouteBundle],
                     marketplace_seller: Optional[str] = None) -> dict:
    s = {
        "id": session_id,
        "status": "ready_for_payment",
        "currency": payment.currency.lower(),
        "line_items": [{"id": "li_1", "item": {"id": "sku_1", "quantity": 1}, "total": payment.amount}],
        "totals": [{"type": "total", "display_text": "Total", "amount": payment.amount}],
        "payment": {"handlers": [{"id": "h1", "name": "dev.acp.tokenized.card", "psp": psp,
                                  "requires_delegate_payment": True}]},
        "capabilities": {"extensions": [{"name": EXTENSION_NAME,
                                         "extends": ["$.CheckoutSession.receiving_authority"]}]},
        "seller": {"name": seller_name},
    }
    if marketplace_seller:
        s["marketplace_seller_details"] = {"name": marketplace_seller}
    if bundle is not None and bundle.rap.binding is not None:
        s["receiving_authority"] = {
            "payee": payment.payee,
            "route_digest": route_digest(bundle),
            "binding_digest": bundle.rap.binding.digest,
        }
    return s


def allowance(payment: Payment, session_id: str, merchant_id: str) -> dict:
    exp = dt.datetime.fromtimestamp(payment.t + 900, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"reason": "one_time", "max_amount": payment.amount, "currency": payment.currency.lower(),
            "checkout_session_id": session_id, "merchant_id": merchant_id, "expires_at": exp}


def mint_delegated_payment(session: dict, payment: Payment, bundle: Optional[RouteBundle], anchor: str,
                           policy: Policy, trust: TrustStore) -> Tuple[Decision, Optional[dict]]:
    ra = session.get("receiving_authority")
    if ra is None or bundle is None:
        return Decision(STEP_UP, reasons=["acp-no-receiving-authority"], stage="acp"), None
    if ra["payee"] != payment.payee:
        return Decision(DENY, reasons=["acp-payee-mismatch"], stage="acp"), None
    if ra["route_digest"] != route_digest(bundle) or bundle.rap.binding is None \
            or ra["binding_digest"] != bundle.rap.binding.digest:
        return Decision(DENY, reasons=["acp-receiving-authority-mismatch"], stage="acp"), None
    total = next((t["amount"] for t in session["totals"] if t["type"] == "total"), None)
    if total != payment.amount:
        return Decision(DENY, reasons=["acp-amount"], stage="acp"), None
    d = verify_route(bundle, payment, anchor, policy, trust)
    d.stage = "acp/" + d.stage
    if d.verdict != ALLOW:
        return d, None
    return d, allowance(payment, session["id"], payment.payee)


def mutations(session: dict) -> List[tuple]:
    out = []
    if "receiving_authority" in session:
        for key, val in (("payee", "proc:evilpsp/acct_000001"), ("route_digest", "0" * 64),
                         ("binding_digest", "f" * 64)):
            m = copy.deepcopy(session)
            m["receiving_authority"][key] = val
            out.append((f"receiving_authority.{key}", m))
        m = copy.deepcopy(session)
        del m["receiving_authority"]
        out.append(("receiving_authority.removed", m))
    m = copy.deepcopy(session)
    m["totals"][0]["amount"] += 100
    out.append(("totals.amount", m))
    m = copy.deepcopy(session)
    m["seller"]["name"] = m["seller"]["name"] + " Official"
    out.append(("seller.name", m))
    return out
