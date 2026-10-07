"""Spent-nonce store for binding tokens.

A binding token is an authorization to pay one payee once. The signature,
payee, amount and expiry checks do not stop the same token from being
presented and executed a second time, so a verifier that wants single use
keeps a store of the tokens it has already allowed. ``claim`` is an atomic
check-and-record: it returns False for a token that was already claimed.

Entries are keyed by (signer, nonce) and kept until the token expires; after
that the token fails the expiry check anyway, so the entry is pruned.
"""

from __future__ import annotations

import threading
from typing import Dict, Tuple

from .pav import BindingToken


class SpentNonces:
    def __init__(self) -> None:
        self._spent: Dict[Tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._spent)

    def is_spent(self, beta: BindingToken) -> bool:
        return (beta.signer_kid, beta.nonce) in self._spent

    def claim(self, beta: BindingToken, now: int) -> bool:
        """Record the token as spent. False if it already was."""
        key = (beta.signer_kid, beta.nonce)
        with self._lock:
            for k in [k for k, exp in self._spent.items() if exp < now]:
                del self._spent[k]
            if key in self._spent:
                return False
            self._spent[key] = beta.exp
            return True
