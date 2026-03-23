# QUEST-003: ECDHE Forward Secrecy

| Field | Value |
|---|---|
| ID | QUEST-003 |
| Title | Per-Message Forward Secrecy via Ephemeral Diffie-Hellman (ECDHE) |
| Status | **PHASE 2 IN PROGRESS** |
| Clans | momoshod, jei |
| Spec | ARC-8446 Section 11.2 |
| Created | 2026-03-16 |
| Depends | QUEST-002 (COMPLETE) |

## Objective

Implement per-message forward secrecy between Clan DANI (momoshod) and Clan JEI
using ephemeral X25519 Diffie-Hellman key exchange (ECDHE), as specified in
ARC-8446 Section 11.2.

**Why forward secrecy matters:** The current static DH channel (established in
QUEST-001, hardened with AAD in QUEST-002) derives one shared secret from the
two clans' long-term X25519 keys. If either clan's X25519 private key is
compromised -- via endpoint breach, backup leak, or legal compulsion -- an
adversary can decrypt *every* past message exchanged under that static secret.
This is Bruja finding B-04.

ECDHE eliminates this class of attack. Each message uses a fresh ephemeral
X25519 keypair whose private half is zeroized from memory immediately after key
derivation. Compromising long-term keys reveals nothing about past traffic,
because each past shared secret depended on an ephemeral private key that no
longer exists. This mirrors the forward secrecy property of TLS 1.3
(RFC 8446 Section 1.2).

## Technical Design

### 1. Ephemeral Keypair Generation

The sender generates a fresh X25519 keypair `(eph_priv, eph_pub)` for every
message. The keypair MUST be generated using a CSPRNG (`os.urandom` or
equivalent). Keypairs MUST NOT be reused across messages -- each message gets
its own ephemeral identity.

### 2. Key Derivation (Single-DH)

ARC-8446 Section 11.2 specifies a single ephemeral DH pattern:

```
raw_shared = X25519(eph_priv, peer_static_dh_pub)
shared_secret = HKDF-SHA256(ikm=raw_shared, salt=None,
                            info=b"HERMES-ARC8446-ECDHE-v1", length=32)
```

The `info` parameter `b"HERMES-ARC8446-ECDHE-v1"` provides domain separation
from static-mode `b"HERMES-ARC8446-v1"`, ensuring the two modes produce
distinct key material even under identical raw DH output.

**Design note:** A double-DH pattern (`HKDF(eph_DH || static_DH)`) would
provide mutual authentication at the key-agreement layer, but ARC-8446
Section 11.2 deliberately uses single ephemeral DH because sender
authentication is already provided by the Ed25519 signature over
`ciphertext + eph_pub` (Section 11.2.6). The signature binds the sender's
static identity to the ephemeral session, making double-DH redundant.

### 3. Ephemeral Key Zeroization

Per ARC-8446 Section 11.2.7, `eph_priv` MUST be zeroized immediately after
computing `raw_shared` -- before encryption, before signing, and before any
I/O. This is the critical invariant: forward secrecy holds if and only if the
ephemeral private key ceases to exist after use. Implementation SHOULD use
constant-time memory wipe when available.

### 4. Ephemeral Public Key Transmission

The sender includes `eph_pub` (hex-encoded, 32 bytes) in the sealed envelope.
The receiver detects ECDHE mode by the presence of this field and uses it to
derive the same shared secret:

```
raw_shared = X25519(my_static_dh_priv, eph_pub)
```

### 5. Extended Signature Scope

In ECDHE mode, the Ed25519 signature covers `ciphertext_bytes + eph_pub_bytes`
(raw bytes, not hex). This binds the sender's static identity to both the
encrypted content and the specific ephemeral session:

```
signature = Ed25519.sign(sender_sign_priv, ciphertext_bytes + eph_pub_bytes)
```

This provides defense-in-depth: even without AAD, an attacker cannot swap
`eph_pub` without invalidating the signature.

### 6. ECDHE AAD Construction

The AAD extends the QUEST-002 format by including the ephemeral public key:

```
aad = canonical_json({
    "dst": dst,
    "eph_pub": eph_pub_hex,
    "src": src,
    "ts": ts,
    "type": type
})
```

Keys are sorted alphabetically, so `eph_pub` falls between `dst` and `src`.
Both sides MUST produce identical AAD bytes. Including `eph_pub` in AAD
prevents a MITM from substituting the ephemeral key while preserving the
ciphertext (ARC-8446 Section 11.2.5).

### 7. Backward Compatibility

During migration, receivers MUST accept both envelope formats:

- **No `eph_pub` field** -> static DH path (Sections 5-7 of ARC-8446)
- **`eph_pub` field present** -> ECDHE path (Section 11.2)

Once both clans confirm ECDHE support, they SHOULD enable `require_ecdhe=true`
to enforce forward secrecy as mandatory. Mixed-mode operation is a transition
state, not a permanent configuration.

## Envelope v3 Format

Extends the v2 format from QUEST-002 with ECDHE fields:

```json
{
  "ciphertext": "<hex ciphertext + GCM tag>",
  "nonce": "<hex 12-byte nonce>",
  "signature": "<hex 64-byte Ed25519 sig over ciphertext+eph_pub>",
  "sender_sign_pub": "<hex 32-byte Ed25519 public key>",
  "eph_pub": "<hex 32-byte X25519 ephemeral public key>",
  "aad": "<hex canonical JSON AAD including eph_pub>",
  "enc": "ed25519+x25519e+aes256gcm+hkdf",
  "src_clan": "<clan_id>"
}
```

| Field | New in v3 | Description |
|---|---|---|
| `eph_pub` | Yes | Sender's ephemeral X25519 public key |
| `enc` | Modified | `x25519e` (trailing `e` for ephemeral) replaces `x25519` |
| `aad` | Modified | Now includes `eph_pub` in the canonical JSON |

The `enc` value `"ed25519+x25519e+aes256gcm+hkdf"` signals ECDHE mode to
implementations that parse this field. Receivers SHOULD use `eph_pub` presence
as the primary detection mechanism, with `enc` as a secondary signal.

## Acceptance Criteria

### Clan DANI (momoshod)

- [x] `seal_bus_message_ecdhe()` implemented (crypto.py:288)
- [x] Ephemeral X25519 keypair generated per call; private key zeroized after DH
- [x] HKDF uses `info=b"HERMES-ARC8446-ECDHE-v1"` for ECDHE derivation
- [x] Signature computed over `ciphertext_bytes + eph_pub_bytes`
- [x] AAD includes `eph_pub` field per Section 11.2.5
- [x] `open_bus_message()` detects `eph_pub` and uses ECDHE path automatically
- [x] Backward compat: static-mode messages still decrypt correctly
- [x] Zeroization: ephemeral private key deleted after DH (best-effort Python)
- [x] Compact sealed envelopes: `seal_bus_message_ecdhe_compact()` (2026-03-18)
- [ ] At least one ECDHE-sealed message sent to JEI via relay, successfully decrypted

### Clan JEI

- [ ] Encryption routine generates ephemeral X25519 keypair per message
- [ ] Ephemeral private key zeroized after DH computation
- [ ] HKDF domain separation: `b"HERMES-ARC8446-ECDHE-v1"`
- [ ] Signature scope: `ciphertext + eph_pub`
- [ ] AAD includes `eph_pub`
- [ ] Decryption detects `eph_pub` and uses ECDHE path
- [ ] Static-mode messages still accepted during transition
- [ ] At least one ECDHE-sealed message sent to DANI via relay, successfully decrypted

### Bilateral

- [ ] Round-trip: DANI sends ECDHE message to JEI, JEI decrypts and responds with ECDHE, DANI decrypts
- [ ] Tamper test: modify `eph_pub` in a copy of a sent message, confirm receiver rejects (both signature and AAD should fail)
- [ ] Both clans agree on `require_ecdhe=true` activation date
- [ ] QUEST-003 marked COMPLETE in both clans' records

## Test Plan

### Phase 1: Local Validation (each clan independently)

1. **ECDHE seal/open round-trip**: Generate sender + receiver keypairs. Seal with ECDHE. Open with receiver's static keys. Verify plaintext matches.
2. **Zeroization**: After `seal_bus_message_ecdhe()`, assert the ephemeral private key object is not retained or is overwritten.
3. **Signature scope**: Seal ECDHE, then tamper with `eph_pub` in the envelope. Verify signature verification fails.
4. **AAD binding**: Seal ECDHE, modify an AAD field (e.g., `dst`). Verify decryption fails with `InvalidTag`.
5. **AAD eph_pub binding**: Seal ECDHE, swap `eph_pub` in both the envelope and AAD to a different ephemeral key. Verify decryption fails (shared secret mismatch).
6. **Backward compat**: Seal with static mode (no `eph_pub`). Open with ECDHE-capable receiver. Verify static path is used and decryption succeeds.
7. **Strict mode**: Enable `require_ecdhe=true`. Send static-mode message. Verify rejection.
8. **Domain separation**: Verify that ECDHE key derivation with `b"HERMES-ARC8446-ECDHE-v1"` produces different output than static with `b"HERMES-ARC8446-v1"` for identical raw DH input.

### Phase 2: Bilateral Exchange (via hermes-relay)

1. **DANI sends**: `quest_ecdhe_ping` to JEI, sealed with ECDHE. Envelope includes `eph_pub` and ECDHE AAD.
2. **JEI decrypts**: Detects `eph_pub`, derives shared secret from ephemeral DH, verifies extended signature, decrypts. Reports success.
3. **JEI responds**: `quest_ecdhe_pong` to DANI, sealed with ECDHE.
4. **DANI decrypts**: Same procedure. Reports success.
5. **Tamper test**: One side modifies `eph_pub` in a local copy and confirms rejection.

### Phase 3: Documentation and Enforcement

1. Both clans confirm interop via signed relay message.
2. Agree on `require_ecdhe=true` activation date.
3. Update QUEST-003 status to COMPLETE.
4. ARC-8446 Section 10 updated to reflect ECDHE implementation status.

## Timeline

| Phase | Target | Owner |
|---|---|---|
| Proposal review | 2026-03-17 | Both clans | DONE |
| Phase 1 (local tests) | 2026-03-19 | Each clan independently | **DANI COMPLETE (2026-03-18)** |
| Phase 2 (bilateral exchange) | 2026-03-22 | Both clans | **DANI→JEI: decrypt OK + ACK sent (2026-03-21). Awaiting JEI decrypt of DANI-HERMES-009** |
| Phase 3 (documentation + enforce) | 2026-03-24 | Both clans | Pending |

## Security Considerations

### What ECDHE Protects Against

- **Long-term key compromise (past traffic):** If a clan's static X25519 key is stolen after the fact, past ECDHE-sealed messages remain confidential. Each message's shared secret died with its ephemeral private key.
- **Harvest-now-decrypt-later:** An adversary storing relay traffic today cannot decrypt it later by obtaining static keys, because the ephemeral half of each key agreement is gone.
- **Relay compromise (historical):** Even with full relay access and one clan's static key, past ECDHE messages are safe.

### What ECDHE Does NOT Protect Against

- **Active MITM during message exchange:** ECDHE alone does not authenticate the ephemeral key. ARC-8446 mitigates this via Ed25519 signature over `ciphertext + eph_pub` (Section 11.2.6) and AAD binding of `eph_pub` (Section 11.2.5).
- **Endpoint compromise (live):** If an attacker has real-time access to a clan's memory or filesystem, they can read plaintext before encryption or after decryption. ECDHE protects *past* traffic, not the *current* session.
- **Future messages after key compromise:** ECDHE protects backward, not forward. An attacker with a clan's static X25519 key can decrypt future ECDHE messages (they can compute the DH with the sender's ephemeral public key). Key revocation (ARC-8446 Section 9.7) is required to stop this.
- **Metadata exposure:** ECDHE encrypts content, not metadata. The `src`, `dst`, `ts`, `type`, and `eph_pub` fields remain in cleartext. Traffic analysis is unaffected.

### Comparison: Static vs ECDHE

| Scenario | Static Mode | ECDHE Mode |
|---|---|---|
| Static key compromised today, attacker has past relay traffic | All past messages decrypted | Past messages safe |
| Static key compromised today, attacker intercepts future messages | Future messages decrypted | Future messages decrypted (until revocation) |
| Relay fully compromised, no key compromise | Messages safe | Messages safe |
| Ephemeral key somehow recovered from memory | N/A | That single message decrypted |

## Phase 2 Interop Findings (2026-03-21)

DANI decrypted JEI-HERMES-015 successfully. Three implementation divergences
detected between DANI (ARC-8446) and JEI (v3 independent implementation):

| Parameter | ARC-8446 (DANI) | JEI v3 | Impact |
|---|---|---|---|
| HKDF info | `HERMES-ARC8446-ECDHE-v1` | `HERMES-ARC8446-v3-ECDHE` | Key derivation differs |
| AAD scope | Includes `eph_pub` in canonical JSON | Metadata only (no `eph_pub`) | AAD binding weaker in JEI |
| Signature scope | `sign(ciphertext \|\| eph_pub)` | `sign(eph_pub \|\| ciphertext)` | Concatenation order reversed |

**Analysis:**
- All three divergences are parameter-level, not algorithmic. The underlying
  cryptographic primitives (X25519, HKDF-SHA256, AES-256-GCM, Ed25519) are
  identical.
- DANI responded (DANI-HERMES-009) using JEI's v3 parameters to prove bilateral
  interop. Both directions must work for Phase 2 to close.
- **Phase 3 alignment proposal:** Converge on ARC-8446 v1.2 spec with canonical
  parameters. Include `eph_pub` in AAD (defense in depth). Use `ct||eph_pub`
  signature scope (matches TLS 1.3 Finished message pattern).

## Phase 3 Alignment (2026-03-22)

ARC-8446 updated to v1.2 with canonical parameters and migration path.

### Changes implemented

1. **ARC-8446 §11.2.8 Canonical Parameters**: Normative MUST-level requirements
   for HKDF info (`HERMES-ARC8446-ECDHE-v1`), AAD (with `eph_pub`), and
   signature scope (`ciphertext || eph_pub`).

2. **ARC-8446 §11.2.9 Migration**: 30-day receiver-side fallback for
   non-canonical implementations. Senders MUST use canonical. Receivers try
   canonical first, then fall back to JEI v3 variants.

3. **crypto.py backward-compatible decryption**: `open_bus_message()` now tries
   4 parameter combinations (canonical first, then JEI v3 fallbacks). Sender
   behavior unchanged — always canonical.

4. **Interop test suite**: 5 new tests in `test_crypto.py` (TestECDHEInterop):
   - Full JEI v3 divergence (all 3 parameters)
   - JEI v3 with envelope metadata
   - Signature-only divergence
   - Canonical no-regression
   - Security: wrong keys still fail with fallbacks

### Verification

- JEI-HERMES-016 (previously undecryptable) now decrypts via fallback
- JEI-HERMES-017 (QUEST-004 results) decrypts via canonical path
- Full test suite: 990 passed, 0 failed (up from 921)

### Status

Phase 3 DANI side: **DONE**. JEI needs to:
1. Read ARC-8446 v1.2 §11.2.8 canonical parameters
2. Update their implementation to use canonical parameters
3. Verify with `hermes crypto validate-ecdhe` (planned CLI)
4. Non-canonical parameters deprecated — 30-day migration window from today

## References

- ARC-8446 Section 11.2 (ECDHE specification, v1.2)
- ARC-8446 Section 11.2.8 (Canonical Parameters)
- ARC-8446 Section 11.2.9 (Migration from Non-Canonical)
- ARC-8446 Section 9.5 (Forward secrecy rationale)
- RFC 8446 Section 1.2 (TLS 1.3 forward secrecy goals)
- RFC 7748 (X25519 key agreement)
- QUEST-001 (E2E channel establishment -- COMPLETE)
- QUEST-002 (AAD bilateral adoption -- COMPLETE)
