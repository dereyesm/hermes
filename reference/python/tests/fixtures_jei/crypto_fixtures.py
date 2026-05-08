"""Cryptography fixtures — QUEST-CROSS-002 bilateral tests.

Uses real cryptography primitives (Ed25519 + X25519 + HKDF-SHA256 + AES-256-GCM).
"""
import os

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization


HKDF_INFO = b"AMARU-ARC8446-ECDHE-v1"
HKDF_ALGO = hashes.SHA256()
HKDF_LENGTH = 32


def _ed25519_keypair() -> dict:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return {
        "private": priv,
        "public": pub,
        "sign_private_hex": priv.private_bytes_raw().hex(),
        "sign_public_hex": pub.public_bytes_raw().hex(),
    }


def _x25519_keypair() -> dict:
    priv = X25519PrivateKey.generate()
    pub = priv.public_key()
    return {
        "private": priv,
        "public": pub,
        "dh_private_hex": priv.private_bytes_raw().hex(),
        "dh_public_hex": pub.public_bytes_raw().hex(),
    }


@pytest.fixture(scope="session")
def ed25519_keypair_jei() -> dict:
    """Real Ed25519 keypair for JEI hub."""
    return _ed25519_keypair()


@pytest.fixture(scope="session")
def ed25519_keypair_dani() -> dict:
    """Real Ed25519 keypair for DANI hub."""
    return _ed25519_keypair()


@pytest.fixture(scope="session")
def x25519_keypair_jei() -> dict:
    """Real X25519 keypair for JEI (for DH key exchange)."""
    return _x25519_keypair()


@pytest.fixture(scope="session")
def x25519_keypair_dani() -> dict:
    """Real X25519 keypair for DANI (for DH key exchange)."""
    return _x25519_keypair()


@pytest.fixture(scope="session")
def shared_secret_bilateral(x25519_keypair_jei, x25519_keypair_dani) -> bytes:
    """X25519 DH shared secret between JEI and DANI."""
    raw = x25519_keypair_jei["private"].exchange(x25519_keypair_dani["public"])
    return raw


@pytest.fixture(scope="function")
def session_key(shared_secret_bilateral, bilateral_session_id) -> bytes:
    """HKDF-SHA256 derived session key using current session_id as salt."""
    hkdf = HKDF(
        algorithm=HKDF_ALGO,
        length=HKDF_LENGTH,
        salt=bilateral_session_id.encode(),
        info=HKDF_INFO,
    )
    return hkdf.derive(shared_secret_bilateral)


@pytest.fixture(scope="function")
def old_session_key(shared_secret_bilateral) -> bytes:
    """HKDF key from a different session — used for replay attack tests."""
    old_session_id = "old-session-id-for-replay-test-9999"
    hkdf = HKDF(
        algorithm=HKDF_ALGO,
        length=HKDF_LENGTH,
        salt=old_session_id.encode(),
        info=HKDF_INFO,
    )
    return hkdf.derive(shared_secret_bilateral)


def sign_test_frame(private_key: Ed25519PrivateKey, frame_dict: dict) -> str:
    """Sign a frame dict with Ed25519. Returns hex-encoded signature."""
    import json
    data = json.dumps(frame_dict, sort_keys=True).encode()
    return private_key.sign(data).hex()


def verify_test_frame(public_key: Ed25519PublicKey, frame_dict: dict, sig_hex: str) -> bool:
    """Verify Ed25519 signature of a frame dict."""
    import json
    data = json.dumps(frame_dict, sort_keys=True).encode()
    try:
        public_key.verify(bytes.fromhex(sig_hex), data)
        return True
    except Exception:
        return False
