"""Simulated ISO 8583 (1987, ASCII) authorization messages.

The issuer's authorization record is MERIDIAN's G1 observer on card rails:
DE32 (acquiring institution id) and DE42 (card acceptor id) identify the
first hop that actually received the authorization, DE43 carries the
acceptor name/location and DE18 the MCC.
"""

from __future__ import annotations

from typing import Dict, Tuple

# field -> (kind, max length, variable-length prefix digits)
SPEC: Dict[int, Tuple[str, int, int]] = {
    2: ("n", 19, 2), 3: ("n", 6, 0), 4: ("n", 12, 0), 7: ("n", 10, 0), 11: ("n", 6, 0), 18: ("n", 4, 0),
    32: ("n", 11, 2), 37: ("an", 12, 0), 38: ("an", 6, 0), 39: ("an", 2, 0), 41: ("ans", 8, 0),
    42: ("ans", 15, 0), 43: ("ans", 40, 0), 49: ("n", 3, 0),
}


def _enc(field_no: int, value: str) -> str:
    kind, n, var = SPEC[field_no]
    if var:
        if len(value) > n:
            raise ValueError(f"DE{field_no} too long")
        return f"{len(value):0{var}d}{value}"
    if kind == "n":
        return value.rjust(n, "0")[-n:]
    return value.ljust(n)[:n]


def pack(mti: str, fields: Dict[int, str]) -> str:
    bits = 0
    for f in fields:
        bits |= 1 << (64 - f)
    body = "".join(_enc(f, fields[f]) for f in sorted(fields))
    return mti + f"{bits:016X}" + body


def unpack(msg: str) -> Tuple[str, Dict[int, str]]:
    mti, bitmap, pos = msg[:4], int(msg[4:20], 16), 20
    out: Dict[int, str] = {}
    for f in range(2, 65):
        if not bitmap >> (64 - f) & 1:
            continue
        kind, n, var = SPEC[f]
        if var:
            ln = int(msg[pos:pos + var])
            pos += var
            out[f] = msg[pos:pos + ln]
            pos += ln
        else:
            raw = msg[pos:pos + n]
            out[f] = raw if kind == "n" else raw.rstrip()
            pos += n
    return mti, out


def authorization_request(pan: str, amount: int, currency_num: str, stan: str, mcc: str, acquirer_iic: str,
                          caid: str, name_loc: str, tid: str = "AGENT001", ts: str = "1006120000") -> str:
    return pack("0100", {2: pan, 3: "000000", 4: str(amount), 7: ts, 11: stan, 18: mcc, 32: acquirer_iic,
                         41: tid, 42: caid, 43: name_loc, 49: currency_num})


def authorization_response(req: str, approved: bool = True, auth_code: str = "A1B2C3") -> str:
    _, f = unpack(req)
    resp = dict(f)
    resp[37] = f.get(11, "0").rjust(12, "0")
    resp[38] = auth_code if approved else "      "
    resp[39] = "00" if approved else "05"
    return pack("0110", resp)


def first_hop_from_record(resp: str, iic_to_acquirer: Dict[str, str]) -> str:
    """Map an issuer authorization record to the rail payee identifier."""
    _, f = unpack(resp)
    acquirer = iic_to_acquirer.get(f[32], f"iic{f[32]}")
    return f"proc:{acquirer}/{f[42].strip()}"
