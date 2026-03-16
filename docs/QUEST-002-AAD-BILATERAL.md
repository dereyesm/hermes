# QUEST-002: Bilateral AAD Adoption

| Field | Value |
|---|---|
| ID | QUEST-002 |
| Title | Bilateral AAD (Associated Authenticated Data) Adoption |
| Status | **COMPLETE** |
| Closed | 2026-03-16 |
| Clans | momoshod, jei |
| Spec | ARC-8446 Section 6.1.1 |
| Created | 2026-03-08 |
| Depends | QUEST-001 (COMPLETE) |

## Objective

Both Clan DANI (momoshod) and Clan JEI adopt AAD binding per ARC-8446 Section 6.1.1, ensuring that message metadata (`dst`, `src`, `ts`, `type`) is cryptographically bound to the ciphertext via AES-256-GCM's Associated Authenticated Data mechanism. This prevents metadata tampering without detection and completes the security hardening initiated in QUEST-001.

## Background

QUEST-001 established the encrypted communication channel between momoshod and jei. During Bruja's security review (JEI-SEC-001), AAD was identified as a critical hardening measure. The mitigation was implemented in ARC-8446 Section 6.1.1 and in DANI's `crypto.py` reference implementation (commit 61bac28), but:

1. **AAD is not yet used in practice.** The hello/hello_ack handshake messages were sent without AAD.
2. **Envelope formats diverge.** DANI's sealed message uses `{ciphertext, nonce, signature, sender_sign_pub}` while JEI uses `{enc, src_clan, nonce, ciphertext, signature}`. AAD adoption requires both sides to agree on which fields constitute the canonical AAD input.
3. **AAD construction must be identical on both sides.** Per ARC-8446 s6.1.1, AAD is the canonical JSON serialization of `{dst, src, ts, type}` with keys sorted alphabetically. Any divergence in serialization causes decryption failure.

## Acceptance Criteria

### Clan DANI (momoshod)

- [x] `seal_bus_message()` calls include AAD parameter with canonical JSON of `{dst, src, ts, type}` for all relay messages.
- [x] `open_bus_message()` calls include the same AAD parameter, reconstructed from the message envelope.
- [x] At least one relay message sent to JEI with AAD bound, successfully decrypted by JEI.
- [x] AAD fields are present and extractable from the outer (unencrypted) envelope of every sealed message.

### Clan JEI

- [x] JEI's encryption routine binds AAD (canonical JSON of `{dst, src, ts, type}`) when calling AES-256-GCM encrypt.
- [x] JEI's decryption routine reconstructs AAD from the message envelope and passes it to AES-256-GCM decrypt.
- [x] At least one relay message sent to DANI with AAD bound, successfully decrypted by DANI.
- [x] AAD fields are present and extractable from the outer envelope of every sealed message.

### Bilateral

- [x] Both clans agree on a unified envelope format that exposes AAD fields in cleartext (see Format Alignment below).
- [x] Round-trip verified: DANI sends AAD-bound message to JEI, JEI decrypts and responds with AAD-bound message, DANI decrypts.
- [x] Format convergence `src_clan` → `src` confirmed bilaterally (JEI-HERMES-010, 2026-03-16).

## Test Plan

### Phase 1: Local Validation (each clan independently)

1. **Positive test**: Seal a message with AAD = `{"dst":"jei","src":"momoshod","ts":"2026-03-08","type":"quest"}` (keys sorted). Open with same AAD. Verify success.
2. **Negative test**: Seal with AAD as above. Attempt to open with modified AAD (e.g., change `dst` to `"other"`). Verify `InvalidTag` / decryption failure.
3. **Serialization test**: Verify canonical JSON output is deterministic: keys alphabetically sorted, no whitespace, UTF-8 encoded.

### Phase 2: Bilateral Exchange (via hermes-relay)

1. **DANI sends**: A `quest_ping` message to JEI with AAD bound. File: `dani_outbox.jsonl` in hermes-relay.
2. **JEI decrypts**: JEI pulls the message, reconstructs AAD from the envelope, decrypts. Reports success/failure.
3. **JEI responds**: A `quest_pong` message to DANI with AAD bound. File: `jei_outbox.jsonl`.
4. **DANI decrypts**: DANI pulls, reconstructs AAD, decrypts. Reports success/failure.
5. **Tamper test**: One side intentionally modifies a cleartext AAD field in a copy of a sent message and confirms the other side's decryption rejects it. (This can be done locally on the receiver's side to avoid polluting the relay.)

### Phase 3: Documentation

1. Both clans confirm interop in a signed message via the relay.
2. Quest is marked COMPLETE in both clans' records.

## Format Alignment

The current envelope formats must converge for AAD to work bilaterally. The proposed unified envelope format for relay messages:

### Current Formats

| Field | DANI | JEI |
|---|---|---|
| Ciphertext | `ciphertext` | `ciphertext` |
| Nonce | `nonce` | `nonce` |
| Signature | `signature` | `signature` |
| Sender identity | `sender_sign_pub` | `src_clan` |
| Algorithm declaration | (implicit) | `enc` |
| AAD metadata | (not present) | (not present) |

### Proposed Envelope (v2)

```json
{
  "src": "momoshod",
  "dst": "jei",
  "ts": "2026-03-08",
  "type": "quest_ping",
  "enc": "aes-256-gcm",
  "nonce": "<hex>",
  "ciphertext": "<hex>",
  "signature": "<hex>",
  "sender_sign_pub": "<hex>"
}
```

**Key decisions:**

| Issue | Resolution |
|---|---|
| AAD fields | `dst`, `src`, `ts`, `type` -- always present in cleartext in the outer envelope |
| AAD serialization | Canonical JSON: `{"dst":"...","src":"...","ts":"...","type":"..."}` (alphabetical keys, no whitespace, UTF-8) |
| `enc` field (from JEI) | Adopted. Declares algorithm explicitly. Value: `"aes-256-gcm"` |
| `sender_sign_pub` (from DANI) | Adopted. Allows signature verification without pre-cached key lookup |
| `src_clan` (JEI) vs `src` (DANI) | Converge to `src` per ARC-5322 field naming. `src_clan` accepted as alias during transition |
| Signature scope | Unchanged: `sign(ciphertext_bytes)` as aligned in QUEST-001 |

**Migration path:** Both sides SHOULD accept messages in either the old or new format during the transition period (detect by presence/absence of AAD fields). Once both sides confirm v2 support, old format is deprecated.

## Timeline

| Phase | Target | Owner |
|---|---|---|
| Proposal review | 2026-03-09 | Both clans |
| Phase 1 (local tests) | 2026-03-10 | Each clan independently |
| Format alignment agreement | 2026-03-11 | Both clans (async via relay) |
| Phase 2 (bilateral exchange) | 2026-03-12 | Both clans |
| Phase 3 (documentation + close) | 2026-03-13 | Both clans |

## Notes

- AAD does NOT encrypt the metadata fields. They remain in cleartext in the envelope. AAD binds them to the ciphertext so tampering is detected.
- If either clan needs more time for implementation, the timeline shifts accordingly. The quest is cooperative, not competitive.
- This quest establishes the pattern for future spec adoption quests between clans.
