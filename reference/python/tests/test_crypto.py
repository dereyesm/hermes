"""Tests for Amaru crypto module — Ed25519 + X25519 + AES-256-GCM."""

import json
import os
import tempfile
from datetime import date

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from amaru.crypto import (
    COMPACT_SEALED_ECDHE_LEN,
    COMPACT_SEALED_STATIC_LEN,
    ClanKeyPair,
    NonceTracker,
    decrypt_message,
    derive_shared_secret,
    derive_shared_secret_ecdhe,
    encrypt_message,
    load_peer_public,
    open_bus_message,
    open_bus_message_compact,
    seal_bus_message,
    seal_bus_message_compact,
    seal_bus_message_ecdhe,
    seal_bus_message_ecdhe_compact,
    sign_message,
    verify_signature,
)


class TestClanKeyPair:
    def test_generate(self):
        kp = ClanKeyPair.generate()
        assert kp.sign_private is not None
        assert kp.sign_public is not None
        assert kp.dh_private is not None
        assert kp.dh_public is not None

    def test_fingerprint_format(self):
        kp = ClanKeyPair.generate()
        fp = kp.fingerprint()
        parts = fp.split(":")
        assert len(parts) == 8
        for part in parts:
            assert len(part) == 4
            int(part, 16)  # must be valid hex

    def test_fingerprint_deterministic(self):
        kp = ClanKeyPair.generate()
        assert kp.fingerprint() == kp.fingerprint()

    def test_different_keys_different_fingerprints(self):
        kp1 = ClanKeyPair.generate()
        kp2 = ClanKeyPair.generate()
        assert kp1.fingerprint() != kp2.fingerprint()

    def test_export_public(self):
        kp = ClanKeyPair.generate()
        pub = kp.export_public()
        assert "sign_public" in pub
        assert "dh_public" in pub
        assert len(pub["sign_public"]) == 64  # 32 bytes hex
        assert len(pub["dh_public"]) == 64

    def test_export_private(self):
        kp = ClanKeyPair.generate()
        priv = kp.export_private()
        assert "sign_private" in priv
        assert "dh_private" in priv
        assert "sign_public" in priv
        assert "dh_public" in priv

    def test_roundtrip_from_private_hex(self):
        kp1 = ClanKeyPair.generate()
        priv = kp1.export_private()
        kp2 = ClanKeyPair.from_private_hex(priv["sign_private"], priv["dh_private"])
        assert kp1.fingerprint() == kp2.fingerprint()
        assert kp1.export_public() == kp2.export_public()

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kp1 = ClanKeyPair.generate()
            kp1.save(tmpdir, "test-clan")

            # Check files exist
            assert os.path.exists(os.path.join(tmpdir, "test-clan.key"))
            assert os.path.exists(os.path.join(tmpdir, "test-clan.pub"))

            # Check private key file permissions
            stat = os.stat(os.path.join(tmpdir, "test-clan.key"))
            assert oct(stat.st_mode)[-3:] == "600"

            # Check public key file contains fingerprint
            with open(os.path.join(tmpdir, "test-clan.pub")) as f:
                pub_data = json.load(f)
            assert "fingerprint" in pub_data

            # Load and verify
            kp2 = ClanKeyPair.load(tmpdir, "test-clan")
            assert kp1.fingerprint() == kp2.fingerprint()

    def test_load_peer_public(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kp = ClanKeyPair.generate()
            kp.save(tmpdir, "peer")
            sign_pub, dh_pub = load_peer_public(tmpdir, "peer")
            assert sign_pub is not None
            assert dh_pub is not None


class TestDiffieHellman:
    def test_shared_secret_symmetric(self):
        """Both sides derive the same shared secret."""
        alice = ClanKeyPair.generate()
        bob = ClanKeyPair.generate()
        secret_a = derive_shared_secret(alice.dh_private, bob.dh_public)
        secret_b = derive_shared_secret(bob.dh_private, alice.dh_public)
        assert secret_a == secret_b

    def test_shared_secret_length(self):
        alice = ClanKeyPair.generate()
        bob = ClanKeyPair.generate()
        secret = derive_shared_secret(alice.dh_private, bob.dh_public)
        assert len(secret) == 32  # 256 bits

    def test_different_peers_different_secrets(self):
        alice = ClanKeyPair.generate()
        bob = ClanKeyPair.generate()
        charlie = ClanKeyPair.generate()
        secret_ab = derive_shared_secret(alice.dh_private, bob.dh_public)
        secret_ac = derive_shared_secret(alice.dh_private, charlie.dh_public)
        assert secret_ab != secret_ac


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        alice = ClanKeyPair.generate()
        bob = ClanKeyPair.generate()
        secret = derive_shared_secret(alice.dh_private, bob.dh_public)
        encrypted = encrypt_message(secret, "Hello from DANI")
        decrypted = decrypt_message(secret, encrypted["nonce"], encrypted["ciphertext"])
        assert decrypted == "Hello from DANI"

    def test_encrypt_produces_hex(self):
        secret = os.urandom(32)
        encrypted = encrypt_message(secret, "test")
        assert isinstance(encrypted["nonce"], str)
        assert isinstance(encrypted["ciphertext"], str)
        bytes.fromhex(encrypted["nonce"])
        bytes.fromhex(encrypted["ciphertext"])

    def test_wrong_key_fails(self):
        secret1 = os.urandom(32)
        secret2 = os.urandom(32)
        encrypted = encrypt_message(secret1, "secret message")
        with pytest.raises(InvalidTag):
            decrypt_message(secret2, encrypted["nonce"], encrypted["ciphertext"])

    def test_tampered_ciphertext_fails(self):
        secret = os.urandom(32)
        encrypted = encrypt_message(secret, "important data")
        tampered = encrypted["ciphertext"][:-2] + "ff"
        with pytest.raises(InvalidTag):
            decrypt_message(secret, encrypted["nonce"], tampered)

    def test_unicode_message(self):
        secret = os.urandom(32)
        msg = "Hola desde el Clan DANI"
        encrypted = encrypt_message(secret, msg)
        decrypted = decrypt_message(secret, encrypted["nonce"], encrypted["ciphertext"])
        assert decrypted == msg

    def test_empty_message(self):
        secret = os.urandom(32)
        encrypted = encrypt_message(secret, "")
        decrypted = decrypt_message(secret, encrypted["nonce"], encrypted["ciphertext"])
        assert decrypted == ""

    def test_long_message(self):
        secret = os.urandom(32)
        msg = "A" * 10000
        encrypted = encrypt_message(secret, msg)
        decrypted = decrypt_message(secret, encrypted["nonce"], encrypted["ciphertext"])
        assert decrypted == msg


class TestSignatures:
    def test_sign_verify(self):
        kp = ClanKeyPair.generate()
        data = b"message to sign"
        sig = sign_message(kp.sign_private, data)
        assert verify_signature(kp.sign_public, data, sig)

    def test_wrong_key_fails_verification(self):
        kp1 = ClanKeyPair.generate()
        kp2 = ClanKeyPair.generate()
        data = b"signed by kp1"
        sig = sign_message(kp1.sign_private, data)
        assert not verify_signature(kp2.sign_public, data, sig)

    def test_tampered_data_fails(self):
        kp = ClanKeyPair.generate()
        data = b"original"
        sig = sign_message(kp.sign_private, data)
        assert not verify_signature(kp.sign_public, b"tampered", sig)

    def test_signature_is_hex(self):
        kp = ClanKeyPair.generate()
        sig = sign_message(kp.sign_private, b"test")
        bytes.fromhex(sig)
        assert len(sig) == 128  # Ed25519 signature = 64 bytes = 128 hex chars


class TestSealOpen:
    def test_seal_open_roundtrip(self):
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        sealed = seal_bus_message(dani, jei.dh_public, "QUEST_PROPOSAL:XC-001")
        plaintext = open_bus_message(jei, dani.sign_public, dani.dh_public, sealed)
        assert plaintext == "QUEST_PROPOSAL:XC-001"

    def test_seal_contains_required_fields(self):
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        sealed = seal_bus_message(dani, jei.dh_public, "test")
        assert "ciphertext" in sealed
        assert "nonce" in sealed
        assert "signature" in sealed
        assert "sender_sign_pub" in sealed

    def test_open_rejects_wrong_signature(self):
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        impostor = ClanKeyPair.generate()

        sealed = seal_bus_message(impostor, jei.dh_public, "fake message")
        # Verify with dani's pubkey — should fail because impostor signed it
        result = open_bus_message(jei, dani.sign_public, impostor.dh_public, sealed)
        assert result is None

    def test_bidirectional_communication(self):
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        # DANI -> JEI
        sealed1 = seal_bus_message(dani, jei.dh_public, "hello from DANI")
        msg1 = open_bus_message(jei, dani.sign_public, dani.dh_public, sealed1)
        assert msg1 == "hello from DANI"

        # JEI -> DANI
        sealed2 = seal_bus_message(jei, dani.dh_public, "hello_ack from JEI")
        msg2 = open_bus_message(dani, jei.sign_public, jei.dh_public, sealed2)
        assert msg2 == "hello_ack from JEI"

    def test_sealed_message_is_json_serializable(self):
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        sealed = seal_bus_message(dani, jei.dh_public, "test message")
        json_str = json.dumps(sealed)
        restored = json.loads(json_str)
        plaintext = open_bus_message(jei, dani.sign_public, dani.dh_public, restored)
        assert plaintext == "test message"


class TestFullFlow:
    """End-to-end test simulating the first inter-clan hello."""

    def test_first_contact_flow(self):
        # 1. Both clans generate keypairs
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        with tempfile.TemporaryDirectory() as keys_dir:
            # 2. Save keys
            dani.save(keys_dir, "momoshod")
            jei.save(keys_dir, "jei")

            # 3. Load peer public keys (simulates exchanging pubkeys)
            jei_sign_pub, jei_dh_pub = load_peer_public(keys_dir, "jei")
            dani_sign_pub, dani_dh_pub = load_peer_public(keys_dir, "momoshod")

            # 4. Verify fingerprints match (in person)
            dani_loaded = ClanKeyPair.load(keys_dir, "momoshod")
            jei_loaded = ClanKeyPair.load(keys_dir, "jei")
            assert dani_loaded.fingerprint() == dani.fingerprint()
            assert jei_loaded.fingerprint() == jei.fingerprint()

            # 5. DANI sends hello
            hello = seal_bus_message(dani, jei_dh_pub, "HELLO:momoshod:amaru_relay_operational")
            relay_line = {
                "ts": "2026-03-08",
                "src": "momoshod",
                "dst": "jei",
                "type": "request",
                "secure": hello,
            }
            relay_json = json.dumps(relay_line)

            # 6. JEI reads from relay, opens message
            relay_received = json.loads(relay_json)
            plaintext = open_bus_message(jei, dani_sign_pub, dani_dh_pub, relay_received["secure"])
            assert plaintext == "HELLO:momoshod:amaru_relay_operational"

            # 7. JEI responds with hello_ack
            ack = seal_bus_message(jei, dani_dh_pub, "HELLO_ACK:jei:ready")
            plaintext_ack = open_bus_message(dani, jei_sign_pub, jei_dh_pub, ack)
            assert plaintext_ack == "HELLO_ACK:jei:ready"


class TestAAD:
    """Tests for Associated Authenticated Data (AAD) in AES-256-GCM."""

    def test_encrypt_decrypt_with_aad(self):
        """AAD roundtrip works when both sides use same AAD."""
        secret = os.urandom(32)
        aad = b'{"dst":"jei","src":"momoshod","ts":"2026-03-08","type":"quest"}'
        encrypted = encrypt_message(secret, "test with aad", aad=aad)
        decrypted = decrypt_message(secret, encrypted["nonce"], encrypted["ciphertext"], aad=aad)
        assert decrypted == "test with aad"

    def test_wrong_aad_fails_decrypt(self):
        """Decryption fails when AAD doesn't match."""
        secret = os.urandom(32)
        aad1 = b'{"dst":"jei","src":"momoshod"}'
        aad2 = b'{"dst":"evil","src":"momoshod"}'
        encrypted = encrypt_message(secret, "test", aad=aad1)
        with pytest.raises(InvalidTag):
            decrypt_message(secret, encrypted["nonce"], encrypted["ciphertext"], aad=aad2)

    def test_aad_none_backward_compatible(self):
        """Messages encrypted without AAD can still be decrypted without AAD."""
        secret = os.urandom(32)
        encrypted = encrypt_message(secret, "no aad")
        decrypted = decrypt_message(secret, encrypted["nonce"], encrypted["ciphertext"])
        assert decrypted == "no aad"

    def test_seal_open_with_envelope_meta(self):
        """seal/open with envelope_meta binds headers to ciphertext."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-08"}
        sealed = seal_bus_message(dani, jei.dh_public, "quest payload", envelope_meta=meta)
        assert "aad" in sealed
        plaintext = open_bus_message(
            jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta
        )
        assert plaintext == "quest payload"

    def test_seal_open_mismatched_meta_fails(self):
        """Opening with different envelope_meta than sealing fails."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta1 = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-08"}
        meta2 = {"src": "momoshod", "dst": "evil", "type": "quest", "ts": "2026-03-08"}
        sealed = seal_bus_message(dani, jei.dh_public, "quest payload", envelope_meta=meta1)
        result = open_bus_message(
            jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta2
        )
        assert result is None

    def test_seal_without_meta_backward_compatible(self):
        """seal/open without envelope_meta still works (backward compat)."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        sealed = seal_bus_message(dani, jei.dh_public, "no meta")
        assert "aad" not in sealed
        plaintext = open_bus_message(jei, dani.sign_public, dani.dh_public, sealed)
        assert plaintext == "no meta"

    def test_old_message_without_aad_opens_even_with_meta(self):
        """Backward compat: old messages (no AAD) open even when caller passes meta."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        # Seal WITHOUT meta (old-style)
        sealed = seal_bus_message(dani, jei.dh_public, "old message")
        # Open WITH meta — should still work (backward compat)
        meta = {"src": "momoshod", "dst": "jei", "type": "hello", "ts": "2026-03-08"}
        plaintext = open_bus_message(
            jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta
        )
        assert plaintext == "old message"


class TestNonceTracker:
    """Tests for NonceTracker replay protection (ARC-8446 §9.5)."""

    def test_new_nonce_returns_true(self):
        """A new nonce should be accepted."""
        tracker = NonceTracker()
        assert tracker.check_and_record("clan_a", "aabbccdd", "2026-03-08") is True

    def test_same_nonce_returns_false(self):
        """A replayed nonce should be rejected."""
        today = date.today().isoformat()
        tracker = NonceTracker()
        assert tracker.check_and_record("clan_a", "aabbccdd", today) is True
        assert tracker.check_and_record("clan_a", "aabbccdd", today) is False

    def test_per_sender_isolation(self):
        """Same nonce from different senders should both be accepted."""
        tracker = NonceTracker()
        assert tracker.check_and_record("clan_a", "aabbccdd", "2026-03-08") is True
        assert tracker.check_and_record("clan_b", "aabbccdd", "2026-03-08") is True

    def test_ttl_eviction(self):
        """Nonces older than TTL should be evicted, allowing reuse."""
        tracker = NonceTracker()
        # Record a nonce with an old timestamp
        old_ts = "2020-01-01"
        assert tracker.check_and_record("clan_a", "old_nonce", old_ts, ttl_days=1) is True
        # The nonce is recorded with old timestamp. Next check_and_record
        # for a different nonce will evict it during _evict_expired.
        # Then the old nonce should be accepted again.
        assert tracker.check_and_record("clan_a", "new_nonce", "2026-03-08", ttl_days=1) is True
        # Now old_nonce should have been evicted
        assert tracker.check_and_record("clan_a", "old_nonce", "2026-03-08", ttl_days=1) is True

    def test_persistence_save_load(self):
        """NonceTracker persists across sessions via JSON file."""
        today = date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "nonces.json")

            # Session 1: record a nonce
            tracker1 = NonceTracker(persistence_path=path)
            assert tracker1.check_and_record("clan_a", "nonce_1", today) is True

            # Session 2: load from file, same nonce should be rejected
            tracker2 = NonceTracker(persistence_path=path)
            assert tracker2.check_and_record("clan_a", "nonce_1", today) is False
            # But a new nonce should be accepted
            assert tracker2.check_and_record("clan_a", "nonce_2", today) is True

    def test_persistence_file_created(self):
        """save() creates the JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "nonces.json")
            tracker = NonceTracker(persistence_path=path)
            tracker.check_and_record("clan_a", "abc123", "2026-03-08")
            assert os.path.exists(path)
            with open(path) as f:
                data = json.load(f)
            assert "clan_a" in data
            assert "abc123" in data["clan_a"]


class TestNonceTrackerIntegration:
    """Tests for open_bus_message with nonce_tracker parameter."""

    def test_open_rejects_replay(self):
        """open_bus_message rejects a replayed message when nonce_tracker is provided."""
        today = date.today().isoformat()
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": today}

        sealed = seal_bus_message(dani, jei.dh_public, "quest payload", envelope_meta=meta)
        tracker = NonceTracker()

        # First open: should succeed
        result1 = open_bus_message(
            jei,
            dani.sign_public,
            dani.dh_public,
            sealed,
            envelope_meta=meta,
            nonce_tracker=tracker,
        )
        assert result1 == "quest payload"

        # Second open with same sealed message: replay detected
        result2 = open_bus_message(
            jei,
            dani.sign_public,
            dani.dh_public,
            sealed,
            envelope_meta=meta,
            nonce_tracker=tracker,
        )
        assert result2 is None

    def test_open_without_tracker_allows_replay(self):
        """Without nonce_tracker, replayed messages are still accepted (backward compat)."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        sealed = seal_bus_message(dani, jei.dh_public, "msg")
        result1 = open_bus_message(jei, dani.sign_public, dani.dh_public, sealed)
        result2 = open_bus_message(jei, dani.sign_public, dani.dh_public, sealed)
        assert result1 == "msg"
        assert result2 == "msg"


class TestECDHE:
    """Tests for ECDHE forward secrecy (ARC-8446 §11.2, QUEST-003)."""

    def test_ecdhe_seal_open_roundtrip(self):
        """Seal with ECDHE, open, verify plaintext matches."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-16"}

        sealed = seal_bus_message_ecdhe(
            dani, jei.dh_public, "QUEST-003 forward secrecy", envelope_meta=meta
        )
        assert "eph_pub" in sealed
        assert sealed["enc"] == "ECDHE-X25519-AES256GCM"

        plaintext = open_bus_message(
            jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta
        )
        assert plaintext == "QUEST-003 forward secrecy"

    def test_ecdhe_domain_separation(self):
        """Same raw DH input produces different keys with ECDHE vs static info strings."""
        priv = X25519PrivateKey.generate()
        peer = X25519PrivateKey.generate().public_key()

        secret_static = derive_shared_secret(priv, peer)
        secret_ecdhe = derive_shared_secret_ecdhe(priv, peer)

        # Same DH raw output, but different HKDF info → different derived keys
        assert secret_static != secret_ecdhe
        assert len(secret_static) == 32
        assert len(secret_ecdhe) == 32

    def test_ecdhe_signature_scope(self):
        """Tamper with eph_pub after seal, verify signature fails."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-16"}

        sealed = seal_bus_message_ecdhe(dani, jei.dh_public, "tamper test", envelope_meta=meta)

        # Replace eph_pub with a different key
        fake_eph = X25519PrivateKey.generate().public_key()
        sealed["eph_pub"] = fake_eph.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

        # Signature verification should fail (signature covers ciphertext + original eph_pub)
        result = open_bus_message(jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta)
        assert result is None

    def test_ecdhe_aad_binding(self):
        """Modify AAD field (e.g. dst), verify decryption fails with InvalidTag."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-16"}

        sealed = seal_bus_message_ecdhe(dani, jei.dh_public, "aad binding test", envelope_meta=meta)

        # Open with modified envelope_meta — AAD mismatch should cause failure
        bad_meta = {"src": "momoshod", "dst": "evil", "type": "quest", "ts": "2026-03-16"}
        result = open_bus_message(
            jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=bad_meta
        )
        assert result is None

    def test_ecdhe_aad_eph_pub_binding(self):
        """Swap eph_pub in envelope to different key, verify decryption fails."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-16"}

        sealed = seal_bus_message_ecdhe(
            dani, jei.dh_public, "eph_pub binding test", envelope_meta=meta
        )

        # Swap eph_pub to a different key. Signature still covers original eph_pub,
        # so this should fail at signature verification. Even if it passed,
        # shared secret derivation would produce wrong key.
        other_eph = X25519PrivateKey.generate().public_key()
        sealed["eph_pub"] = other_eph.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

        result = open_bus_message(jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta)
        assert result is None

    def test_ecdhe_backward_compat(self):
        """Seal with static mode (no eph_pub), open with ECDHE-capable receiver."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-16"}

        # Seal with static mode (old-style)
        sealed = seal_bus_message(dani, jei.dh_public, "static mode msg", envelope_meta=meta)
        assert "eph_pub" not in sealed

        # Open should use static path automatically
        plaintext = open_bus_message(
            jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta
        )
        assert plaintext == "static mode msg"

    def test_ecdhe_ephemeral_key_uniqueness(self):
        """Call seal_bus_message_ecdhe twice, verify eph_pub differs."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        sealed1 = seal_bus_message_ecdhe(dani, jei.dh_public, "msg1")
        sealed2 = seal_bus_message_ecdhe(dani, jei.dh_public, "msg2")

        assert sealed1["eph_pub"] != sealed2["eph_pub"]

    def test_ecdhe_open_detects_mode(self):
        """Verify open_bus_message automatically detects ECDHE vs static."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-16"}

        # ECDHE message
        sealed_ecdhe = seal_bus_message_ecdhe(dani, jei.dh_public, "ecdhe msg", envelope_meta=meta)
        assert "eph_pub" in sealed_ecdhe

        # Static message
        sealed_static = seal_bus_message(dani, jei.dh_public, "static msg", envelope_meta=meta)
        assert "eph_pub" not in sealed_static

        # Both should open correctly with the same open_bus_message function
        plain_ecdhe = open_bus_message(
            jei, dani.sign_public, dani.dh_public, sealed_ecdhe, envelope_meta=meta
        )
        plain_static = open_bus_message(
            jei, dani.sign_public, dani.dh_public, sealed_static, envelope_meta=meta
        )
        assert plain_ecdhe == "ecdhe msg"
        assert plain_static == "static msg"


class TestECDHEPostSunset:
    """Tests verifying non-canonical ECDHE is rejected after fallback sunset (ARC-8446 §11.2.9)."""

    def test_non_canonical_hkdf_rejected(self):
        """Messages using JEI v3 HKDF info string are rejected after sunset."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM

        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        # Seal with non-canonical HKDF info (old JEI v3)
        eph_private = X25519PrivateKey.generate()
        eph_public = eph_private.public_key()
        eph_pub_hex = eph_public.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

        raw_shared = eph_private.exchange(dani.dh_public)
        hkdf = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None,
            info=b"HERMES-ARC8446-v3-ECDHE",  # Non-canonical
        )
        shared_secret = hkdf.derive(raw_shared)

        meta = {"src": "jei", "dst": "momoshod", "type": "quest", "ts": "2026-04-02"}
        aad = json.dumps(meta, sort_keys=True, separators=(",", ":")).encode("utf-8")

        nonce = os.urandom(12)
        aesgcm = _AESGCM(shared_secret)
        ct = aesgcm.encrypt(nonce, b"non-canonical msg", aad)

        ct_bytes = ct
        eph_bytes = bytes.fromhex(eph_pub_hex)
        sig = sign_message(jei.sign_private, ct_bytes + eph_bytes)

        sealed = {
            "ciphertext": ct.hex(),
            "nonce": nonce.hex(),
            "signature": sig,
            "sender_sign_pub": jei.sign_public.public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
            "eph_pub": eph_pub_hex,
            "enc": "ECDHE-X25519-AES256GCM",
        }

        result = open_bus_message(dani, jei.sign_public, jei.dh_public, sealed, envelope_meta=meta)
        assert result is None, "Non-canonical HKDF should be rejected after fallback sunset"

    def test_non_canonical_aad_rejected(self):
        """Messages with AAD missing eph_pub are rejected after sunset."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM

        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        # Seal with canonical HKDF but AAD without eph_pub
        eph_private = X25519PrivateKey.generate()
        eph_public = eph_private.public_key()
        eph_pub_hex = eph_public.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

        raw_shared = eph_private.exchange(dani.dh_public)
        hkdf = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None,
            info=b"HERMES-ARC8446-ECDHE-v1",  # Canonical HKDF
        )
        shared_secret = hkdf.derive(raw_shared)

        meta = {"src": "jei", "dst": "momoshod", "type": "quest", "ts": "2026-04-02"}
        # AAD WITHOUT eph_pub (non-canonical)
        aad = json.dumps(meta, sort_keys=True, separators=(",", ":")).encode("utf-8")

        nonce = os.urandom(12)
        aesgcm = _AESGCM(shared_secret)
        ct = aesgcm.encrypt(nonce, b"bad aad msg", aad)

        ct_bytes = ct
        eph_bytes = bytes.fromhex(eph_pub_hex)
        sig = sign_message(jei.sign_private, ct_bytes + eph_bytes)

        sealed = {
            "ciphertext": ct.hex(),
            "nonce": nonce.hex(),
            "signature": sig,
            "sender_sign_pub": jei.sign_public.public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
            "eph_pub": eph_pub_hex,
            "enc": "ECDHE-X25519-AES256GCM",
        }

        result = open_bus_message(dani, jei.sign_public, jei.dh_public, sealed, envelope_meta=meta)
        assert result is None, "AAD without eph_pub should be rejected after fallback sunset"

    def test_canonical_ecdhe_still_works(self):
        """Canonical ECDHE messages still decrypt (regression guard)."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-04-02"}

        sealed = seal_bus_message_ecdhe(dani, jei.dh_public, "canonical msg", envelope_meta=meta)
        result = open_bus_message(jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta)
        assert result == "canonical msg"


class TestCompactSealedEnvelope:
    """Tests for compact sealed envelope format (ARC-5322 §14 + ARC-8446)."""

    def test_static_compact_roundtrip(self):
        """Seal compact static, open compact, verify plaintext."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-17"}

        sealed = seal_bus_message_compact(dani, jei.dh_public, "compact static", envelope_meta=meta)
        assert isinstance(sealed, list)
        assert len(sealed) == COMPACT_SEALED_STATIC_LEN

        plaintext = open_bus_message_compact(
            jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta
        )
        assert plaintext == "compact static"

    def test_ecdhe_compact_roundtrip(self):
        """Seal compact ECDHE, open compact, verify plaintext."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-17"}

        sealed = seal_bus_message_ecdhe_compact(
            dani, jei.dh_public, "compact ecdhe", envelope_meta=meta
        )
        assert isinstance(sealed, list)
        assert len(sealed) == COMPACT_SEALED_ECDHE_LEN

        plaintext = open_bus_message_compact(
            jei, dani.sign_public, dani.dh_public, sealed, envelope_meta=meta
        )
        assert plaintext == "compact ecdhe"

    def test_static_compact_array_structure(self):
        """Verify compact static array has [ct, nonce, sig, pub, aad]."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        sealed = seal_bus_message_compact(dani, jei.dh_public, "structure test")
        assert len(sealed) == 5
        # All elements should be hex strings
        for i, elem in enumerate(sealed):
            assert isinstance(elem, str), f"Element {i} should be string"

    def test_ecdhe_compact_array_structure(self):
        """Verify compact ECDHE array has [ct, nonce, sig, pub, aad, eph_pub]."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        sealed = seal_bus_message_ecdhe_compact(dani, jei.dh_public, "structure test")
        assert len(sealed) == 6
        # eph_pub (index 5) should be 64 hex chars (32 bytes X25519 public key)
        assert len(sealed[5]) == 64

    def test_compact_is_json_serializable(self):
        """Compact envelope should survive JSON round-trip."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-17"}

        sealed = seal_bus_message_ecdhe_compact(
            dani, jei.dh_public, "json roundtrip", envelope_meta=meta
        )
        json_str = json.dumps(sealed)
        restored = json.loads(json_str)

        plaintext = open_bus_message_compact(
            jei, dani.sign_public, dani.dh_public, restored, envelope_meta=meta
        )
        assert plaintext == "json roundtrip"

    def test_compact_rejects_wrong_length(self):
        """Open compact should reject arrays with wrong element count."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        result = open_bus_message_compact(jei, dani.sign_public, dani.dh_public, ["a", "b", "c"])
        assert result is None

    def test_compact_rejects_non_list(self):
        """Open compact should reject non-list input."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        result = open_bus_message_compact(jei, dani.sign_public, dani.dh_public, {"not": "a list"})
        assert result is None

    def test_compact_vs_verbose_same_crypto(self):
        """Compact and verbose seal should produce equivalent crypto operations."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-17"}

        # Seal verbose, open compact (cross-format should NOT work — different nonces)
        # But sealing + opening in same format should always work
        sealed_v = seal_bus_message(dani, jei.dh_public, "verbose", envelope_meta=meta)
        sealed_c = seal_bus_message_compact(dani, jei.dh_public, "compact", envelope_meta=meta)

        plain_v = open_bus_message(
            jei, dani.sign_public, dani.dh_public, sealed_v, envelope_meta=meta
        )
        plain_c = open_bus_message_compact(
            jei, dani.sign_public, dani.dh_public, sealed_c, envelope_meta=meta
        )
        assert plain_v == "verbose"
        assert plain_c == "compact"

    def test_ecdhe_compact_ephemeral_uniqueness(self):
        """Each ECDHE compact seal generates a unique eph_pub."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        s1 = seal_bus_message_ecdhe_compact(dani, jei.dh_public, "msg1")
        s2 = seal_bus_message_ecdhe_compact(dani, jei.dh_public, "msg2")
        assert s1[5] != s2[5]  # eph_pub at index 5

    def test_compact_without_envelope_meta(self):
        """Compact seal/open works without envelope_meta."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        sealed = seal_bus_message_compact(dani, jei.dh_public, "no meta")
        plaintext = open_bus_message_compact(jei, dani.sign_public, dani.dh_public, sealed)
        assert plaintext == "no meta"

    def test_ecdhe_compact_without_envelope_meta(self):
        """ECDHE compact seal/open works without envelope_meta."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()

        sealed = seal_bus_message_ecdhe_compact(dani, jei.dh_public, "no meta ecdhe")
        plaintext = open_bus_message_compact(jei, dani.sign_public, dani.dh_public, sealed)
        assert plaintext == "no meta ecdhe"

    def test_compact_size_savings(self):
        """Compact envelope should be smaller than verbose when serialized."""
        dani = ClanKeyPair.generate()
        jei = ClanKeyPair.generate()
        meta = {"src": "momoshod", "dst": "jei", "type": "quest", "ts": "2026-03-17"}

        sealed_v = seal_bus_message_ecdhe(dani, jei.dh_public, "size test", envelope_meta=meta)
        sealed_c = seal_bus_message_ecdhe_compact(
            dani, jei.dh_public, "size test", envelope_meta=meta
        )

        json_v = json.dumps(sealed_v, separators=(",", ":"))
        json_c = json.dumps(sealed_c, separators=(",", ":"))

        # Compact removes key names → should be smaller
        assert len(json_c) < len(json_v)
