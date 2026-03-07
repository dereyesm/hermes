"""Tests for HERMES crypto module — Ed25519 + X25519 + AES-256-GCM."""

import json
import os
import tempfile

import pytest

from hermes.crypto import (
    ClanKeyPair,
    decrypt_message,
    derive_shared_secret,
    encrypt_message,
    load_peer_public,
    open_bus_message,
    seal_bus_message,
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
        with pytest.raises(Exception):
            decrypt_message(secret2, encrypted["nonce"], encrypted["ciphertext"])

    def test_tampered_ciphertext_fails(self):
        secret = os.urandom(32)
        encrypted = encrypt_message(secret, "important data")
        tampered = encrypted["ciphertext"][:-2] + "ff"
        with pytest.raises(Exception):
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
            hello = seal_bus_message(dani, jei_dh_pub, "HELLO:momoshod:hermes_relay_operational")
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
            plaintext = open_bus_message(
                jei, dani_sign_pub, dani_dh_pub, relay_received["secure"]
            )
            assert plaintext == "HELLO:momoshod:hermes_relay_operational"

            # 7. JEI responds with hello_ack
            ack = seal_bus_message(jei, dani_dh_pub, "HELLO_ACK:jei:ready")
            plaintext_ack = open_bus_message(dani, jei_sign_pub, jei_dh_pub, ack)
            assert plaintext_ack == "HELLO_ACK:jei:ready"
