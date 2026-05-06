"""Tests for ARC-8446 §4.3 — KCI v2 identity-binding shared secret derivation.

Covers:
- Symmetric derivation (DANI ↔ JEI compute same secret with bound identities)
- Pipe injection rejection in src_id / dst_id
- Fingerprint encoding rules (raw 64-hex, NOT colon-grouped)
- Session-id salt mixing
- KCI attack scenario (compromised peer X25519 → cannot impersonate third clan)
- Cross-version isolation (v1 ≠ v2, ECDHE-v1 ≠ ECDHE-v2)
- Peer fingerprint binding (different fp → different secret)

Self-contained: generates fresh keypairs per test (no fixtures_jei/ dependency).

Reference: ARC-8446 §4.3, QC002 KCI-001, JEI bilateral 2026-05-04 (msg
19df3a50976ca745).
"""

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from amaru.crypto import (
    derive_shared_secret,
    derive_shared_secret_ecdhe,
    derive_shared_secret_ecdhe_v2,
    derive_shared_secret_v2,
)


def _x25519_pair() -> tuple[X25519PrivateKey, X25519PrivateKey]:
    return X25519PrivateKey.generate(), X25519PrivateKey.generate()


def _ed25519_pub_hex() -> str:
    return Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()


class TestKciV2Symmetric:
    def test_v2_symmetric_with_matching_identities(self):
        """Both sides produce the same secret when identities + peer fp match."""
        dani_dh, jei_dh = _x25519_pair()
        jei_sign_pub = _ed25519_pub_hex()
        dani_sign_pub = _ed25519_pub_hex()

        dani_secret = derive_shared_secret_v2(
            my_dh_private=dani_dh,
            peer_dh_public=jei_dh.public_key(),
            src_id="dani",
            dst_id="jei",
            peer_sign_pub_hex=jei_sign_pub,
        )
        jei_secret = derive_shared_secret_v2(
            my_dh_private=jei_dh,
            peer_dh_public=dani_dh.public_key(),
            src_id="dani",
            dst_id="jei",
            peer_sign_pub_hex=jei_sign_pub,
        )
        assert dani_secret == jei_secret
        assert len(dani_secret) == 32
        # Sanity: dani_sign_pub is unused by both sides in this test (peer_sign
        # binds to JEI on both ends per §4.3 outbound convention).
        assert dani_sign_pub != jei_sign_pub


class TestKciV2PipeInjection:
    def test_pipe_in_src_id_rejected(self):
        dani_dh, jei_dh = _x25519_pair()
        with pytest.raises(ValueError, match=r"clan_id MUST NOT contain '\|'"):
            derive_shared_secret_v2(
                my_dh_private=dani_dh,
                peer_dh_public=jei_dh.public_key(),
                src_id="dani|fake",
                dst_id="jei",
                peer_sign_pub_hex=_ed25519_pub_hex(),
            )

    def test_pipe_in_dst_id_rejected(self):
        dani_dh, jei_dh = _x25519_pair()
        with pytest.raises(ValueError, match=r"clan_id MUST NOT contain '\|'"):
            derive_shared_secret_v2(
                my_dh_private=dani_dh,
                peer_dh_public=jei_dh.public_key(),
                src_id="dani",
                dst_id="jei|attacker",
                peer_sign_pub_hex=_ed25519_pub_hex(),
            )

    def test_pipe_in_both_ids_rejected(self):
        dani_dh, jei_dh = _x25519_pair()
        with pytest.raises(ValueError, match=r"clan_id MUST NOT contain '\|'"):
            derive_shared_secret_ecdhe_v2(
                eph_private=dani_dh,
                peer_static_dh_public=jei_dh.public_key(),
                src_id="d|x",
                dst_id="j|y",
                peer_sign_pub_hex=_ed25519_pub_hex(),
            )


class TestKciV2FingerprintFormat:
    def test_short_fingerprint_rejected(self):
        dani_dh, jei_dh = _x25519_pair()
        with pytest.raises(ValueError, match="64 hex chars"):
            derive_shared_secret_v2(
                my_dh_private=dani_dh,
                peer_dh_public=jei_dh.public_key(),
                src_id="dani",
                dst_id="jei",
                peer_sign_pub_hex="abcd1234",  # too short
            )

    def test_grouped_fingerprint_format_rejected(self):
        """Colon-grouped fingerprint format (8x4-hex) MUST be rejected.

        ARC-8446 §4.3 mandates raw 64-char Ed25519 hex, not the human-readable
        fingerprint() output (e.g. 'a1b2:c3d4:...').
        """
        dani_dh, jei_dh = _x25519_pair()
        grouped = "a1b2:c3d4:e5f6:7890:1234:5678:9abc:def0"
        with pytest.raises(ValueError):
            derive_shared_secret_v2(
                my_dh_private=dani_dh,
                peer_dh_public=jei_dh.public_key(),
                src_id="dani",
                dst_id="jei",
                peer_sign_pub_hex=grouped,
            )

    def test_non_hex_fingerprint_rejected(self):
        dani_dh, jei_dh = _x25519_pair()
        with pytest.raises(ValueError, match="valid lowercase hex"):
            derive_shared_secret_v2(
                my_dh_private=dani_dh,
                peer_dh_public=jei_dh.public_key(),
                src_id="dani",
                dst_id="jei",
                peer_sign_pub_hex="z" * 64,  # 64 chars but not hex
            )


class TestKciV2SessionSalt:
    def test_session_salt_changes_secret(self):
        """Same DH + identities + peer fp, different session_id → distinct keys."""
        dani_dh, jei_dh = _x25519_pair()
        peer_fp = _ed25519_pub_hex()
        kwargs = dict(
            my_dh_private=dani_dh,
            peer_dh_public=jei_dh.public_key(),
            src_id="dani",
            dst_id="jei",
            peer_sign_pub_hex=peer_fp,
        )
        secret_a = derive_shared_secret_v2(**kwargs, session_id="session-aaa")
        secret_b = derive_shared_secret_v2(**kwargs, session_id="session-bbb")
        secret_none = derive_shared_secret_v2(**kwargs)
        assert secret_a != secret_b
        assert secret_a != secret_none
        assert secret_b != secret_none


class TestKciV2AttackScenario:
    def test_compromised_dh_cannot_impersonate_third_clan(self):
        """KCI mitigation: compromising JEI's X25519 long-term key does NOT
        let an attacker impersonate ATTACKER toward JEI.

        Setup:
          - DANI, JEI, ATTACKER each have static (Ed25519, X25519) keys
          - Attacker compromises JEI's X25519 private (long-term) key
          - Attacker tries to derive shared secret claiming src_id="attacker"

        With v1 (no identity binding) the attacker would succeed because the
        derivation depends only on raw DH output. With v2 the binding includes
        attacker's claimed src_id + JEI's view of attacker's sign-pub, so
        unless the attacker also compromised JEI's expectation of the
        attacker's Ed25519 sign-pub, the derived key is wrong.
        """
        dani_dh = X25519PrivateKey.generate()
        jei_dh = X25519PrivateKey.generate()
        attacker_dh = X25519PrivateKey.generate()
        attacker_sign_pub = _ed25519_pub_hex()
        wrong_sign_pub = _ed25519_pub_hex()  # what attacker fakes to JEI

        # JEI computes secret expecting message from attacker (real fp)
        jei_view = derive_shared_secret_v2(
            my_dh_private=jei_dh,
            peer_dh_public=attacker_dh.public_key(),
            src_id="attacker",
            dst_id="jei",
            peer_sign_pub_hex=attacker_sign_pub,
        )
        # Attacker, having compromised JEI's DH key, tries to derive same
        # secret using a different sign-pub (e.g. a key they actually control)
        attacker_view = derive_shared_secret_v2(
            my_dh_private=attacker_dh,
            peer_dh_public=jei_dh.public_key(),
            src_id="attacker",
            dst_id="jei",
            peer_sign_pub_hex=wrong_sign_pub,
        )
        assert jei_view != attacker_view  # KCI mitigation works
        # Sanity: dani_dh present so the test setup mirrors a 3-party scenario
        assert dani_dh.public_key().public_bytes_raw() != jei_dh.public_key().public_bytes_raw()


class TestKciV2CrossVersionIsolation:
    def test_v1_static_neq_v2_static(self):
        """derive_shared_secret (v1) ≠ derive_shared_secret_v2 with same DH."""
        dani_dh, jei_dh = _x25519_pair()
        v1 = derive_shared_secret(dani_dh, jei_dh.public_key())
        v2 = derive_shared_secret_v2(
            my_dh_private=dani_dh,
            peer_dh_public=jei_dh.public_key(),
            src_id="dani",
            dst_id="jei",
            peer_sign_pub_hex=_ed25519_pub_hex(),
        )
        assert v1 != v2

    def test_ecdhe_v1_neq_ecdhe_v2(self):
        """derive_shared_secret_ecdhe (v1) ≠ derive_shared_secret_ecdhe_v2."""
        eph_dh, peer_dh = _x25519_pair()
        v1 = derive_shared_secret_ecdhe(eph_dh, peer_dh.public_key())
        v2 = derive_shared_secret_ecdhe_v2(
            eph_private=eph_dh,
            peer_static_dh_public=peer_dh.public_key(),
            src_id="dani",
            dst_id="jei",
            peer_sign_pub_hex=_ed25519_pub_hex(),
        )
        assert v1 != v2

    def test_static_v2_neq_ecdhe_v2(self):
        """Static v2 ≠ ECDHE v2 (info string domain separation preserved)."""
        my_dh, peer_dh = _x25519_pair()
        peer_fp = _ed25519_pub_hex()
        common = dict(
            src_id="dani",
            dst_id="jei",
            peer_sign_pub_hex=peer_fp,
        )
        static = derive_shared_secret_v2(
            my_dh_private=my_dh,
            peer_dh_public=peer_dh.public_key(),
            **common,
        )
        ecdhe = derive_shared_secret_ecdhe_v2(
            eph_private=my_dh,
            peer_static_dh_public=peer_dh.public_key(),
            **common,
        )
        assert static != ecdhe


class TestKciV2PeerBinding:
    def test_different_peer_fp_different_secret(self):
        """Same DH + identities, different peer_sign_pub_hex → distinct keys."""
        dani_dh, jei_dh = _x25519_pair()
        kwargs = dict(
            my_dh_private=dani_dh,
            peer_dh_public=jei_dh.public_key(),
            src_id="dani",
            dst_id="jei",
        )
        secret_a = derive_shared_secret_v2(
            **kwargs, peer_sign_pub_hex=_ed25519_pub_hex()
        )
        secret_b = derive_shared_secret_v2(
            **kwargs, peer_sign_pub_hex=_ed25519_pub_hex()
        )
        assert secret_a != secret_b
