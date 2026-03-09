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
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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
    sign_hex = data.get("sign_public") or data.get("ed25519_pub")
    dh_hex = data.get("dh_public") or data.get("x25519_pub")
    if not sign_hex or not dh_hex:
        raise KeyError("Public key file must contain sign_public/ed25519_pub and dh_public/x25519_pub")
    sign_pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(sign_hex))
    dh_pub = X25519PublicKey.from_public_bytes(bytes.fromhex(dh_hex))
    return sign_pub, dh_pub


def derive_shared_secret(
    my_dh_private: X25519PrivateKey, peer_dh_public: X25519PublicKey
) -> bytes:
    """Derive a shared secret using X25519 Diffie-Hellman + HKDF-SHA256.

    The raw DH output is processed through HKDF-SHA256 with domain-specific
    info parameter to produce a uniformly distributed 256-bit key suitable
    for AES-256-GCM. The info parameter provides domain separation per
    ARC-8446 §5.1.
    """
    raw_shared = my_dh_private.exchange(peer_dh_public)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"HERMES-ARC8446-v1",
    )
    return hkdf.derive(raw_shared)


def encrypt_message(shared_secret: bytes, plaintext: str, aad: bytes | None = None) -> dict:
    """Encrypt a message using AES-256-GCM.

    Returns dict with 'nonce' and 'ciphertext' as hex strings.
    Optional aad (Associated Authenticated Data) binds metadata to ciphertext.
    """
    nonce = os.urandom(12)
    aesgcm = AESGCM(shared_secret)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
    return {
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
    }


def decrypt_message(
    shared_secret: bytes, nonce_hex: str, ciphertext_hex: str, aad: bytes | None = None
) -> str:
    """Decrypt an AES-256-GCM encrypted message."""
    aesgcm = AESGCM(shared_secret)
    plaintext = aesgcm.decrypt(
        bytes.fromhex(nonce_hex),
        bytes.fromhex(ciphertext_hex),
        aad,
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


def _build_aad(envelope_meta: dict | None) -> bytes | None:
    """Build canonical AAD bytes from envelope metadata."""
    if envelope_meta is None:
        return None
    return json.dumps(envelope_meta, sort_keys=True, separators=(",", ":")).encode("utf-8")


def seal_bus_message(
    my_keys: ClanKeyPair,
    peer_dh_public: X25519PublicKey,
    msg: str,
    envelope_meta: dict | None = None,
) -> dict:
    """Encrypt + sign a bus message for relay transmission.

    Returns a dict ready to be written as the 'secure' field in a relay message.
    If envelope_meta is provided, it is used as AAD to cryptographically bind
    the envelope headers (src, dst, type, ts) to the ciphertext.
    """
    aad = _build_aad(envelope_meta)
    shared_secret = derive_shared_secret(my_keys.dh_private, peer_dh_public)
    encrypted = encrypt_message(shared_secret, msg, aad=aad)

    ciphertext_bytes = bytes.fromhex(encrypted["ciphertext"])
    signature = sign_message(my_keys.sign_private, ciphertext_bytes)

    result = {
        "ciphertext": encrypted["ciphertext"],
        "nonce": encrypted["nonce"],
        "signature": signature,
        "sender_sign_pub": my_keys.sign_public.public_bytes(
            Encoding.Raw, PublicFormat.Raw
        ).hex(),
    }
    if aad is not None:
        result["aad"] = aad.hex()
    return result


def open_bus_message(
    my_keys: ClanKeyPair,
    peer_sign_public: Ed25519PublicKey,
    peer_dh_public: X25519PublicKey,
    sealed: dict,
    envelope_meta: dict | None = None,
    nonce_tracker: "NonceTracker | None" = None,
) -> str | None:
    """Verify signature + decrypt a sealed bus message.

    Returns the plaintext message, or None if verification fails.
    If envelope_meta is provided, it is used as AAD for decryption.
    If the sealed message contains an 'aad' field, it must match the
    constructed AAD — otherwise decryption is rejected.
    If nonce_tracker is provided, checks the nonce for replay before
    decryption and rejects replayed messages (ARC-8446 §9.5).
    """
    ciphertext_bytes = bytes.fromhex(sealed["ciphertext"])
    if not verify_signature(peer_sign_public, ciphertext_bytes, sealed["signature"]):
        return None

    # Replay protection: check nonce before decryption
    if nonce_tracker is not None:
        sender = ""
        if envelope_meta and "src" in envelope_meta:
            sender = envelope_meta["src"]
        timestamp = ""
        if envelope_meta and "ts" in envelope_meta:
            timestamp = envelope_meta["ts"]
        if not nonce_tracker.check_and_record(sender, sealed["nonce"], timestamp):
            return None

    aad = _build_aad(envelope_meta)

    # AAD consistency check: if sealed has aad field, verify it matches
    if "aad" in sealed and aad is not None:
        if sealed["aad"] != aad.hex():
            return None
    elif "aad" in sealed and aad is None:
        # Message was sealed with AAD but caller didn't provide envelope_meta
        # Reconstruct from the stored AAD for decryption
        aad = bytes.fromhex(sealed["aad"])
    elif "aad" not in sealed and aad is not None:
        # Old message without AAD — decrypt without AAD for backward compat
        aad = None

    shared_secret = derive_shared_secret(my_keys.dh_private, peer_dh_public)
    try:
        return decrypt_message(shared_secret, sealed["nonce"], sealed["ciphertext"], aad=aad)
    except Exception:
        return None


class NonceTracker:
    """Tracks received nonces to prevent replay attacks (ARC-8446 §9.5).

    Maintains a per-sender nonce set bounded by TTL window.
    Persists across sessions via JSON file.
    """

    def __init__(self, persistence_path: str | None = None):
        self._seen: dict[str, dict[str, str]] = {}  # {sender: {nonce_hex: timestamp_iso}}
        self._persistence_path = persistence_path
        if persistence_path and os.path.exists(persistence_path):
            self.load()

    def check_and_record(
        self, sender: str, nonce_hex: str, timestamp: str, ttl_days: int = 7
    ) -> bool:
        """Check if nonce was seen before. Record it if new.

        Returns True if OK (not replayed), False if replay detected.
        """
        self._evict_expired(sender, ttl_days)

        if sender not in self._seen:
            self._seen[sender] = {}

        if nonce_hex in self._seen[sender]:
            return False

        # Use provided timestamp, or current time if empty
        ts = timestamp if timestamp else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._seen[sender][nonce_hex] = ts

        if self._persistence_path:
            self.save()

        return True

    def _evict_expired(self, sender: str, ttl_days: int) -> None:
        """Remove nonces older than TTL."""
        if sender not in self._seen:
            return

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=ttl_days)
        to_remove = []

        for nonce_hex, ts_str in self._seen[sender].items():
            try:
                # Support both date-only and datetime formats
                if "T" in ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                if ts < cutoff:
                    to_remove.append(nonce_hex)
            except (ValueError, TypeError):
                # If timestamp can't be parsed, keep the nonce (safe default)
                pass

        for nonce_hex in to_remove:
            del self._seen[sender][nonce_hex]

    def save(self) -> None:
        """Persist nonce-set to JSON file."""
        if not self._persistence_path:
            return
        os.makedirs(os.path.dirname(self._persistence_path) or ".", exist_ok=True)
        with open(self._persistence_path, "w") as f:
            json.dump(self._seen, f, indent=2)

    def load(self) -> None:
        """Load nonce-set from JSON file."""
        if not self._persistence_path or not os.path.exists(self._persistence_path):
            return
        with open(self._persistence_path) as f:
            self._seen = json.load(f)
