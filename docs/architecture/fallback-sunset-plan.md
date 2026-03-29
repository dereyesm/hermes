# Fallback Crypto Sunset Plan — ARC-8446 v1.2 §11.2.9

> Migration window: 30 days from canonical confirmation (2026-03-25 → **2026-04-24**)

## Context

ARC-8446 v1.2 §11.2.9 established a 30-day migration window during which
receivers accept ECDHE messages sealed with JEI v3 divergent parameters.
JEI confirmed canonical alignment on 2026-03-25 (JEI-HERMES-018). The
fallback is no longer needed for JEI→DANI messages, but the code remains
for the migration window.

## What Gets Removed

### 1. `_build_aad_no_eph()` (crypto.py:256-262)

```python
def _build_aad_no_eph(envelope_meta: dict) -> bytes:
    """Build AAD without ephemeral public key (JEI v3 compat)."""
```

**Purpose**: Constructs AAD without eph_pub for JEI v3 messages that omitted it.
**Callers**: `open_bus_message()` line 439 only.
**Action**: DELETE function.

### 2. `_ECDHE_HKDF_INFO_JEI_V3` (crypto.py:266)

```python
_ECDHE_HKDF_INFO_JEI_V3 = b"HERMES-ARC8446-v3-ECDHE"
```

**Purpose**: JEI v3 HKDF info string (different from canonical `HERMES-ARC8446-ECDHE-v1`).
**Callers**: `open_bus_message()` lines 449, 451, 458.
**Action**: DELETE constant.

### 3. Fallback attempts in `open_bus_message()` (crypto.py:443-474)

Current code tries 4+ decryption attempts in priority order:
```python
attempts = [
    (b"HERMES-ARC8446-ECDHE-v1", aad_with_eph),      # 1. Canonical
    (b"HERMES-ARC8446-ECDHE-v1", aad_without_eph),    # 2. AAD divergence
    (_ECDHE_HKDF_INFO_JEI_V3, aad_without_eph),       # 3. Full JEI v3
    (_ECDHE_HKDF_INFO_JEI_V3, aad_with_eph),          # 4. Unlikely combo
]
# Plus stored AAD fallbacks (lines 456-461)
```

**After sunset**: Only attempt 1 (canonical) remains. The loop becomes a single try:
```python
shared_secret = _derive_ecdhe_secret(my_keys.dh_private, eph_public,
                                      b"HERMES-ARC8446-ECDHE-v1")
return decrypt_message(shared_secret, sealed["nonce"],
                       sealed["ciphertext"], aad=aad_with_eph)
```

**Action**: Replace 4-attempt loop with single canonical decryption.

### 4. Stored AAD fallback (crypto.py:456-461)

```python
if "aad" in sealed and envelope_meta is None:
    stored_aad = bytes.fromhex(sealed["aad"])
    for hkdf_info in [...]:
        ...
```

**Purpose**: Uses the AAD stored in the sealed envelope as last resort.
**Action**: DELETE block. Post-sunset, AAD is always reconstructed from envelope_meta.

## Tests That Change

| Test file | Test class/method | Lines | Action |
|-----------|-------------------|-------|--------|
| test_crypto.py | `TestECDHEJeiV3Interop` (entire class) | ~635-737 | DELETE — JEI v3 interop no longer needed |
| test_crypto.py | `test_ecdhe_backward_compat` | ~579 | REVIEW — may need update if it tests fallback path |
| test_crypto.py | `test_aad_none_backward_compatible` | ~338 | KEEP — static path backward compat (not ECDHE fallback) |
| test_crypto.py | `test_seal_without_meta_backward_compatible` | ~365-371 | KEEP — envelope_meta=None is valid canonical behavior |

**Estimated test delta**: -5 to -8 tests removed, +2 new tests added (verify fallback rejection).

## Files Changed

| File | Lines changed | Type |
|------|---------------|------|
| `hermes/crypto.py` | ~30 lines removed, ~5 simplified | Code |
| `tests/test_crypto.py` | ~80 lines removed, ~15 added | Tests |
| `spec/ARC-8446.md` | Update §11.2.9: migration COMPLETE | Spec |

## Pre-Sunset Checklist

- [ ] Hub bilateral test Mar 31 — verify canonical ECDHE works in real-time
- [ ] Confirm no JEI v3 messages remain unprocessed in any bus
- [ ] Asciinema bilateral recording (evidence of canonical working)
- [ ] Tag release v0.4.3-alpha (pre-sunset snapshot)

## Execution (Target: 2026-04-24)

1. Remove `_build_aad_no_eph`, `_ECDHE_HKDF_INFO_JEI_V3`
2. Simplify `open_bus_message` ECDHE path to single canonical attempt
3. Remove stored AAD fallback block
4. Delete `TestECDHEJeiV3Interop` test class
5. Add `test_non_canonical_ecdhe_rejected` — verify old params fail
6. Update ARC-8446 §11.2.9: "Migration window closed [date]"
7. Run full suite, verify 0 regressions
8. Commit: `refactor(crypto): sunset ECDHE fallback — ARC-8446 §11.2.9 migration complete`

## Risk

**Low**. JEI canonical confirmed. No other clans use ECDHE yet (Nymyka has
bilateral keys but no ECDHE messages exchanged). The fallback only existed
for JEI v3 divergence, which is resolved.
