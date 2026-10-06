"""Identifiers and the five identity layers (L0-L4).

    brand:<domain>                 L0  brand as displayed
    lei:<20 chars>                 L1  legal entity
    mor:<platform>/<local id>      L2  merchant of record / platform account
    proc:<operator>/<local id>     L3  processing account (PSP account, payfac
                                       sub-merchant, acquirer MID + CAID)
    acct:<bank>/<hash>             L4  bank account (hashed)
    chain:<caip2>/<address>        L4  wallet / escrow contract address
"""

from __future__ import annotations

from .canon import short_hash

L0, L1, L2, L3, L4 = 0, 1, 2, 3, 4

_PREFIX_LAYER = {"brand": L0, "lei": L1, "mor": L2, "proc": L3, "acct": L4, "chain": L4}


def layer(identifier: str) -> int:
    prefix = identifier.split(":", 1)[0]
    try:
        return _PREFIX_LAYER[prefix]
    except KeyError:
        raise ValueError(f"unknown identifier namespace: {identifier!r}") from None


def namespace(identifier: str) -> str:
    """The part an operator controls, e.g. 'proc:stripe' for 'proc:stripe/acct_1'."""
    prefix, rest = identifier.split(":", 1)
    if prefix in ("brand", "lei"):
        return identifier
    if prefix == "chain":
        # chain:eip155:84532/0xabc -> namespace is the chain itself
        return f"chain:{rest.rsplit('/', 1)[0]}"
    return f"{prefix}:{rest.split('/', 1)[0]}"


def brand_id(domain: str) -> str:
    return f"brand:{domain.lower()}"


def bank_account(bank: str, iban: str) -> str:
    return f"acct:{bank}/{short_hash(iban.replace(' ', '').upper())}"


def chain_address(caip2: str, address: str) -> str:
    return f"chain:{caip2}/{address.lower()}"


def is_terminal(identifier: str) -> bool:
    return layer(identifier) == L4


def make_lei(seed: str) -> str:
    """A syntactically valid ISO 17442 LEI (mod 97-10 check digits) from a seed."""
    body = (short_hash(seed, 32).upper())
    alnum = "".join(c for c in body if c.isalnum())[:16]
    base = "5493" + alnum[:14]
    numeric = "".join(str(int(c, 36)) for c in base + "00")
    check = 98 - int(numeric) % 97
    return f"{base}{check:02d}"


def lei_valid(lei: str) -> bool:
    if len(lei) != 20 or not lei.isalnum():
        return False
    numeric = "".join(str(int(c, 36)) for c in lei.upper())
    return int(numeric) % 97 == 1
