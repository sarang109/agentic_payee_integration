"""Signing keys (Ed25519 and ES256) and a counter for signature checks."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

from .canon import b64u, sha256

ED25519 = "Ed25519"
ES256 = "ES256"
ETH = "ETH"  # secp256k1 with EIP-191 personal_sign, verified by address recovery


class SigCounter:
    """Counts signature verifications so experiments can report 2k+1 costs."""

    def __init__(self) -> None:
        self._local = threading.local()

    @property
    def value(self) -> int:
        return getattr(self._local, "n", 0)

    def bump(self) -> None:
        self._local.n = self.value + 1

    def reset(self) -> int:
        n = self.value
        self._local.n = 0
        return n


SIG_CHECKS = SigCounter()


@dataclass(frozen=True)
class PublicKey:
    alg: str
    raw: bytes

    @property
    def kid(self) -> str:
        return "k_" + sha256(self.alg.encode() + self.raw).hex()[:20]

    @property
    def address(self) -> str:
        if self.alg != ETH:
            raise ValueError("only ETH keys have an address")
        return "0x" + self.raw.hex()

    def to_jwk(self) -> dict:
        if self.alg == ETH:
            return {"kty": "EC", "crv": "secp256k1", "addr": self.address}
        if self.alg == ED25519:
            return {"kty": "OKP", "crv": "Ed25519", "x": b64u(self.raw)}
        x, y = self.raw[1:33], self.raw[33:65]
        return {"kty": "EC", "crv": "P-256", "x": b64u(x), "y": b64u(y)}

    def verify(self, sig: bytes, msg: bytes) -> bool:
        SIG_CHECKS.bump()
        try:
            if self.alg == ETH:
                from eth_account import Account
                from eth_account.messages import encode_defunct

                rec = Account.recover_message(encode_defunct(primitive=msg), signature=sig)
                return rec.lower() == self.address.lower()
            if self.alg == ED25519:
                ed25519.Ed25519PublicKey.from_public_bytes(self.raw).verify(sig, msg)
            else:
                if len(sig) != 64:
                    return False
                pk = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), self.raw)
                der = encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big"))
                pk.verify(der, msg, ec.ECDSA(hashes.SHA256()))
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False
        except Exception:  # eth-keys raises its own BadSignature types
            if self.alg == ETH:
                return False
            raise


@dataclass
class KeyPair:
    alg: str = ED25519
    _sk: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._sk is None:
            if self.alg == ETH:
                from eth_account import Account

                self._sk = Account.create()
            elif self.alg == ED25519:
                self._sk = ed25519.Ed25519PrivateKey.generate()
            elif self.alg == ES256:
                self._sk = ec.generate_private_key(ec.SECP256R1())
            else:
                raise ValueError(f"unsupported alg {self.alg}")

    @classmethod
    def from_seed(cls, seed: bytes, alg: str = ED25519) -> "KeyPair":
        """Deterministic keys for reproducible benchmark worlds (test keys only)."""
        s = sha256(b"meridian-test-key|" + seed)
        if alg == ETH:
            from eth_account import Account

            return cls(alg, Account.from_key(s))
        if alg == ED25519:
            return cls(alg, ed25519.Ed25519PrivateKey.from_private_bytes(s))
        n = int("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16)
        d = int.from_bytes(s, "big") % (n - 1) + 1
        return cls(alg, ec.derive_private_key(d, ec.SECP256R1()))

    @property
    def public(self) -> PublicKey:
        if self.alg == ETH:
            return PublicKey(ETH, bytes.fromhex(self._sk.address[2:]))
        if self.alg == ED25519:
            raw = self._sk.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
        else:
            raw = self._sk.public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        return PublicKey(self.alg, raw)

    @property
    def kid(self) -> str:
        return self.public.kid

    def sign(self, msg: bytes) -> bytes:
        if self.alg == ETH:
            from eth_account.messages import encode_defunct

            return bytes(self._sk.sign_message(encode_defunct(primitive=msg)).signature)
        if self.alg == ED25519:
            return self._sk.sign(msg)
        der = self._sk.sign(msg, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")
