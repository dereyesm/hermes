"""HERMES Crypto Module — Ed25519 + X25519 + AES-256-GCM.

Implements the cryptographic stack for inter-clan message security:
- Ed25519: digital signatures (authenticity + integrity)
- X25519: Diffie-Hellman key agreement (shared secret derivation)
- AES-256-GCM: authenticated encryption (confidentiality)

Reference: ARC-8446 (planned), RFC 8446 (TLS 1.3 key schedule pattern).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


@dataclass
class ClanKeyPair:
    """A clan's cryptographic identity: signing key + key agreement key."""

    sign_private: Ed25519PrivateKey
    sign_public: Ed25519PublicKey
    dh_private: X25519PrivateKey
    dh_public: X25519PublicKey

    @staticmethod
    def generate() -> "ClanKeyPair":
        """Generate a new keypair for a clan."""
        sign_private = Ed25519PrivateKey.generate()
        dh_private = X25519PrivateKey.generate()
        return ClanKeyPair(
            sign_private=sign_private,
            sign_public=sign_private.public_key(),
            dh_private=dh_private,
            dh_public=dh_private.public_key(),
        )

    def fingerprint(self) -> str:
        """Human-readable fingerprint of public keys (for in-person verification).

        Format: 8 groups of 4 hex chars separated by colons.
        Example: a1b2:c3d4:e5f6:7890:1234:5678:9abc:def0
        """
        sign_bytes = self.sign_public.public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        dh_bytes = self.dh_public.public_bytes(Encoding.Raw, PublicFormat.Raw)
        combined = hashlib.sha256(sign_bytes + dh_bytes).digest()
        hex_str = combined.hex()[:32]
        return ":".join(hex_str[i : i + 4] for i in range(0, 32, 4))

    def export_public(self) -> dict:
        """Export public keys as hex strings (for sharing)."""
        return {
            "sign_public": self.sign_public.public_bytes(
                Encoding.Raw, PublicFormat.Raw
            ).hex(),
            "dh_public": self.dh_public.public_bytes(
                Encoding.Raw, PublicFormat.Raw
            ).hex(),
        }

    def export_private(self) -> dict:
        """Export private keys as hex strings (for local storage only)."""
        return {
            "sign_private": self.sign_private.private_bytes(
                Encoding.Raw, PrivateFormat.Raw, NoEncryption()
            ).hex(),
            "dh_private": self.dh_private.private_bytes(
                Encoding.Raw, PrivateFormat.Raw, NoEncryption()
            ).hex(),
            **self.export_public(),
        }

    @staticmethod
    def from_private_hex(sign_hex: str, dh_hex: str) -> "ClanKeyPair":
        """Reconstruct keypair from hex-encoded private keys."""
        sign_private = Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(sign_hex)
        )
        dh_private = X25519PrivateKey.from_private_bytes(
            bytes.fromhex(dh_hex)
        )
        return ClanKeyPair(
            sign_private=sign_private,
            sign_public=sign_private.public_key(),
            dh_private=dh_private,
            dh_public=dh_private.public_key(),
        )

    def save(self, directory: str, clan_id: str) -> None:
        """Save keypair to files. Private key stays local, public is shareable."""
        os.makedirs(directory, exist_ok=True)
        private_data = self.export_private()
        public_data = self.export_public()
        public_data["fingerprint"] = self.fingerprint()

        private_path = os.path.join(directory, f"{clan_id}.key")
        public_path = os.path.join(directory, f"{clan_id}.pub")

        with open(private_path, "w") as f:
            json.dump(private_data, f, indent=2)
        os.chmod(private_path, 0o600)

        with open(public_path, "w") as f:
            json.dump(public_data, f, indent=2)

    @staticmethod
    def load(directory: str, clan_id: str) -> "ClanKeyPair":
        """Load keypair from files."""
        private_path = os.path.join(directory, f"{clan_id}.key")
        with open(private_path) as f:
            data = json.load(f)
        return ClanKeyPair.from_private_hex(data["sign_private"], data["dh_private"])


def load_peer_public(directory: str, clan_id: str) -> tuple[Ed25519PublicKey, X25519PublicKey]:
    """Load a peer clan's public keys from their .pub file."""
    public_path = os.path.join(directory, f"{clan_id}.pub")
    with open(public_path) as f:
        data = json.load(f)
    sign_pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(data["sign_public"]))
    dh_pub = X25519PublicKey.from_public_bytes(bytes.fromhex(data["dh_public"]))
    return sign_pub, dh_pub


def derive_shared_secret(
    my_dh_private: X25519PrivateKey, peer_dh_public: X25519PublicKey
) -> bytes:
    """Derive a shared secret using X25519 Diffie-Hellman + HKDF.

    The raw DH output is passed through HKDF-SHA256 to produce a
    uniformly random 256-bit key suitable for AES-256-GCM.
    """
    raw_shared = my_dh_private.exchange(peer_dh_public)
    return HKDF(
        algorithm=SHA256(),
        length=32,
        salt=None,
        info=b"hermes-relay-v1",
    ).derive(raw_shared)


def encrypt_message(shared_secret: bytes, plaintext: str) -> dict:
    """Encrypt a message using AES-256-GCM.

    Returns dict with 'nonce' and 'ciphertext' as hex strings.
    """
    nonce = os.urandom(12)
    aesgcm = AESGCM(shared_secret)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return {
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
    }


def decrypt_message(shared_secret: bytes, nonce_hex: str, ciphertext_hex: str) -> str:
    """Decrypt an AES-256-GCM encrypted message."""
    aesgcm = AESGCM(shared_secret)
    plaintext = aesgcm.decrypt(
        bytes.fromhex(nonce_hex),
        bytes.fromhex(ciphertext_hex),
        None,
    )
    return plaintext.decode("utf-8")


def sign_message(sign_private: Ed25519PrivateKey, data: bytes) -> str:
    """Sign data with Ed25519. Returns hex-encoded signature."""
    return sign_private.sign(data).hex()


def verify_signature(sign_public: Ed25519PublicKey, data: bytes, signature_hex: str) -> bool:
    """Verify an Ed25519 signature. Returns True if valid."""
    try:
        sign_public.verify(bytes.fromhex(signature_hex), data)
        return True
    except Exception:
        return False


def seal_bus_message(
    my_keys: ClanKeyPair,
    peer_dh_public: X25519PublicKey,
    msg: str,
) -> dict:
    """Encrypt + sign a bus message for relay transmission.

    Returns a dict ready to be written as the 'secure' field in a relay message:
    {
        "ciphertext": "...",
        "nonce": "...",
        "signature": "...",
        "sender_sign_pub": "...",
    }
    """
    shared_secret = derive_shared_secret(my_keys.dh_private, peer_dh_public)
    encrypted = encrypt_message(shared_secret, msg)

    ciphertext_bytes = bytes.fromhex(encrypted["ciphertext"])
    signature = sign_message(my_keys.sign_private, ciphertext_bytes)

    return {
        "ciphertext": encrypted["ciphertext"],
        "nonce": encrypted["nonce"],
        "signature": signature,
        "sender_sign_pub": my_keys.sign_public.public_bytes(
            Encoding.Raw, PublicFormat.Raw
        ).hex(),
    }


def open_bus_message(
    my_keys: ClanKeyPair,
    peer_sign_public: Ed25519PublicKey,
    peer_dh_public: X25519PublicKey,
    sealed: dict,
) -> str | None:
    """Verify signature + decrypt a sealed bus message.

    Returns the plaintext message, or None if verification fails.
    """
    ciphertext_bytes = bytes.fromhex(sealed["ciphertext"])
    if not verify_signature(peer_sign_public, ciphertext_bytes, sealed["signature"]):
        return None

    shared_secret = derive_shared_secret(my_keys.dh_private, peer_dh_public)
    return decrypt_message(shared_secret, sealed["nonce"], sealed["ciphertext"])
