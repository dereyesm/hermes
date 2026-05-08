"""Message frame fixtures — QUEST-CROSS-002 bilateral tests.

All frames use the real HELLO→CHALLENGE→AUTH→AUTH_OK protocol from amaru/hub.py.
"""

import os
import time
import uuid

import pytest


@pytest.fixture
def frame_hello(ed25519_keypair_jei) -> dict:
    """Valid HELLO frame from JEI."""
    return {
        "type": "hello",
        "clan_id": "jei",
        "sign_pub": ed25519_keypair_jei["sign_public_hex"],
        "protocol_version": "0.5.0",
        "capabilities": ["e2e_crypto", "store_forward"],
        "role": "peer",
    }


@pytest.fixture
def frame_challenge() -> dict:
    """CHALLENGE frame from hub."""
    return {
        "type": "challenge",
        "nonce": os.urandom(32).hex(),
        "server_version": "0.5.0",
        "server_clan_id": "hub-central",
        "server_capabilities": ["store_forward", "e2e_passthrough", "presence"],
    }


@pytest.fixture
def frame_auth(frame_challenge, ed25519_keypair_jei) -> dict:
    """AUTH frame — signs the nonce with real Ed25519 key."""
    nonce_bytes = bytes.fromhex(frame_challenge["nonce"])
    sig = ed25519_keypair_jei["private"].sign(nonce_bytes).hex()
    return {
        "type": "auth",
        "nonce_response": sig,
    }


@pytest.fixture
def frame_auth_ok() -> dict:
    """AUTH_OK frame from hub."""
    return {
        "type": "auth_ok",
        "clan_id": "hub-central",
        "queue_depth": 0,
    }


@pytest.fixture
def frame_message(bilateral_session_id) -> dict:
    """Valid encrypted message JEI→DANI with receipt request."""
    return {
        "type": "msg",
        "src": "jei",
        "dst": "dani",
        "ref": str(uuid.uuid4()),
        "msg": "<ARC-8446 encrypted payload>",
        "receipt": ["SENT", "DELIVERED"],
        "ttl": 604800,
        "ts": time.time(),
    }


@pytest.fixture
def frame_sent_receipt(frame_message, ed25519_keypair_jei) -> dict:
    """SENT receipt emitted by hub (Ed25519 signed)."""
    import json

    receipt = {
        "type": "receipt",
        "stage": "SENT",
        "ref": frame_message["ref"],
        "ts": time.time(),
    }
    data = json.dumps(receipt, sort_keys=True).encode()
    receipt["signature"] = ed25519_keypair_jei["private"].sign(data).hex()
    return receipt


@pytest.fixture
def frame_delivered_receipt(frame_message) -> dict:
    """DELIVERED receipt emitted on reconnect (QUEUED → DELIVERED)."""
    return {
        "type": "receipt",
        "stage": "DELIVERED",
        "ref": frame_message["ref"],
        "ts": time.time(),
    }


@pytest.fixture
def frame_queued_receipt(frame_message) -> dict:
    """QUEUED receipt emitted at enqueue (option A semantics — ARC-4601 §18.4)."""
    return {
        "type": "receipt",
        "stage": "QUEUED",
        "ref": frame_message["ref"],
        "ts": time.time(),
    }


@pytest.fixture
def frame_fake_sender(bilateral_session_id) -> dict:
    """Message with spoofed sender — for ASI07-01 dispatcher hijack test."""
    return {
        "type": "msg",
        "src": "attacker-fake-identity",
        "dst": "dani",
        "ref": str(uuid.uuid4()),
        "msg": "<malicious payload>",
        "receipt": ["SENT"],
        "ttl": 604800,
        "ts": time.time(),
    }


@pytest.fixture
def frame_replay(frame_message) -> dict:
    """Message with old timestamp — for ASI02-04 replay attack test."""
    return {**frame_message, "ts": time.time() - 7200}  # 2 hours ago


@pytest.fixture
def frame_offline_queue(bilateral_session_id) -> dict:
    """Message destined for offline peer — triggers store-and-forward."""
    return {
        "type": "msg",
        "src": "jei",
        "dst": "dani-offline",
        "ref": str(uuid.uuid4()),
        "msg": "<ARC-8446 encrypted payload for offline peer>",
        "receipt": ["SENT", "QUEUED", "DELIVERED"],
        "ttl": 604800,
        "ts": time.time(),
    }


@pytest.fixture
def frame_unknown_channel(bilateral_session_id) -> dict:
    """Message with unknown channel — for Test 5 channel discrimination."""
    return {
        "type": "msg",
        "src": "jei",
        "dst": "dani",
        "channel": "admin-secret",
        "ref": str(uuid.uuid4()),
        "msg": "<payload>",
        "ts": time.time(),
    }
