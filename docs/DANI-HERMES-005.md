# DANI-HERMES-005 — Response to JEI-HERMES-005

| Field | Value |
|-------|-------|
| From | Clan DANI (MomoshoD) |
| To | Clan JEI (La Triada) |
| Date | 2026-03-09 |
| Re | JEI-HERMES-005 (Co-authorship + Security Review) |
| Status | RESPONSE |

---

## 1. Co-authorship ARC-8446 — Accepted

Confirmed and mutual. Jeimmy Gomez is listed as co-author via Security Review
attribution in ARC-8446 since commit `61bac28`. The spec header reads:

```
Author: HERMES Contributors, Clan JEI (Security Review)
```

Two independent implementations converging on the same protocol is the strongest
validation a spec can get. This is exactly what open standards need.

## 2. Bruja's Security Review — Status Report

Bruja's review is thorough and professional. Here is the current status of each
finding against the HERMES codebase:

| # | Finding | Severity | Status | Evidence |
|---|---------|----------|--------|----------|
| B-01 | Key Revocation | CRITICAL | **RESOLVED** | ARC-8446 §9.7 — full REVOKE procedure with out-of-band notification + re-TOFU. Commit `61bac28`. |
| B-02 | Nonce Replay Registry | MEDIUM | **RESOLVED** | ARC-8446 §9.6 (spec) + `NonceTracker` class in `crypto.py` with per-sender tracking, TTL eviction, JSON persistence. Integrated into `open_bus_message()`. |
| B-03 | AAD in AES-256-GCM | MEDIUM | **RESOLVED** | ARC-8446 §6.1.1 — canonical JSON AAD with backward compatibility. `_build_aad()` + full integration in seal/open. Commit `61bac28`. |
| B-04 | Forward Secrecy (ECDHE) | MEDIUM | **ROADMAP** | ARC-8446 §9.5 documents the limitation. §11.2 specifies ephemeral DH design. Correct for v1 — prioritized for v2. |
| B-05 | HKDF vs SHA-256 | MEDIUM | **RESOLVED** | ARC-8446 §5.1 migrated to `HKDF-SHA256(ikm=raw_DH, salt=None, info=b"HERMES-ARC8446-v1")`. Domain separation active. See Migration Note below. |
| B-06 | Threat Model | LOW | **RESOLVED** | ARC-8446 §9.1 — formal adversary model: assets, in-scope (attacker-in-the-relay, network observer), out-of-scope (endpoint compromise, side-channel, DoS), security guarantees table. |

**Score: 6/6 findings addressed. 5 resolved, 1 roadmapped (B-04).**

### HKDF Migration Note (B-05)

This is a **breaking change** in key derivation. The relay message for QUEST-002
is now sealed with HKDF. To decrypt:

```python
# OLD (SHA-256 direct):
# shared_secret = hashlib.sha256(raw_shared).digest()

# NEW (HKDF-SHA256 with domain separation):
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

raw_shared = my_dh_private.exchange(peer_dh_public)
hkdf = HKDF(
    algorithm=hashes.SHA256(),
    length=32,
    salt=None,
    info=b"HERMES-ARC8446-v1",
)
shared_secret = hkdf.derive(raw_shared)
```

The `enc` field in the sealed envelope signals the KDF version:
- `ed25519+x25519+aes256gcm` → SHA-256 (legacy)
- `ed25519+x25519+aes256gcm+hkdf` → HKDF-SHA256 (current)

Receivers SHOULD support both during the migration window.

## 3. QUEST-001 — Bilateral Closure

Our QUEST-001 (ARC-8446 security hardening from Bruja's review) is **COMPLETE**
on the DANI side. We propose bilateral closure:

- **DANI deliverables**: B-01 (§9.7), B-02 (`NonceTracker`), B-03 (§6.1.1 AAD),
  B-05 (HKDF §5.1), B-06 (§9.1 threat model) — all implemented and tested.
- **JEI deliverables**: Security review completed, findings documented.
- **Bilateral validation**: Two independent implementations of ARC-8446.

QUEST-001 status: **COMPLETE** (pending JEI confirmation).

## 4. QUEST-002 — Re-sent

The original QUEST-002 message (2026-03-08) was unreadable due to format
incompatibility. The sealed envelope used DANI's format (`sender_sign_pub`,
no `enc`/`src_clan`) which JEI's parser didn't recognize.

**Fixed and re-sent** (2026-03-09):
- Added `enc` and `src_clan` fields (JEI format)
- Sealed with HKDF-SHA256 (new KDF — see migration note above)
- AAD binding active
- Same plaintext: proposal for bilateral AAD adoption

Full proposal: `docs/QUEST-002-AAD-BILATERAL.md` in the public repo.

## 5. Proposed QUEST-003: Forward Secrecy (B-04)

With B-01 through B-06 addressed, the remaining finding is B-04 (forward
secrecy via ephemeral DH). We propose QUEST-003 as the next bilateral
deliverable:

**QUEST-003: Ephemeral Key Exchange (ECDHE)**
- Spec: Extend ARC-8446 §11.2 into a full section
- Design: Per-session ephemeral X25519 keypair included in sealed envelope
- Goal: Compromise of long-term DH key does not expose past messages
- Timeline: After QUEST-002 bilateral AAD is confirmed

This is the last major cryptographic gap before ARC-8446 reaches production
grade.

## 6. Implementation Stats

| Metric | Value |
|--------|-------|
| Specs | 15 IMPLEMENTED |
| Tests | 427 passing |
| Modules | 11 Python |
| Crypto tests | 44 (was 36, +8 for NonceTracker) |
| Bruja findings resolved | 5/6 (B-04 roadmapped) |

---

Daniel Reyes — Protocol Architect, Clan DANI (MomoshoD)
Ref: DANI-HERMES-005 | HERMES v0.3.0-alpha | ARC-8446 v1.1
