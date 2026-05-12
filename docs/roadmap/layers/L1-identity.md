---
title: L1 — Identity
type: layer
status: live
percent: 100
depends_on: ["[[L0-foundation]]"]
---

# L1 — Identity

Cryptographic identity. Every clan, every agent, every message is signed.

## Components

| Component | Spec | Status | Code |
|---|---|---|---|
| Ed25519 signatures | ARC-8446 | live ✅ | `amaru/crypto.py` |
| X25519 ECDHE | ARC-8446 | live ✅ | `amaru/crypto.py` |
| AES-256-GCM | ARC-8446 | live ✅ | `amaru/crypto.py` |
| HKDF-SHA256 key derivation | ARC-8446 §4.4 (v2) | live ✅ | `amaru/crypto.py` |
| KCI v2 identity binding | ARC-8446 §4.4 (PR #17) | live ✅ | `amaru/crypto.py:derive_shared_secret_v2` |
| Downgrade protection | ARC-4601 §15.1 (PR #15) | live ✅ | `amaru/hub.py` (err 1002) |
| Rate limiting | Bruja #1 (PR #15) | live ✅ | `amaru/hub.py` |
| Queue backpressure | Bruja #10 (PR #15) | live ✅ | `amaru/hub.py` (err 503) |

## What it enables

- **Soberanía**: keys generated locally, no issuer authority
- **Trust**: every message has a verifiable origin
- **Future reputation**: [[L5-reputation]] builds on these signatures

## Why it matters for the metaverse

Without identity:
- Reputation cannot exist
- Constitution cannot be enforced (who violated what?)
- Marketplace cannot exist (who bid, who delivered?)

## Recent hardening

- **2026-05-04 PR #15**: 3× P0 Bruja audit blockers shipped (downgrade, rate-limit, queue)
- **2026-05-07 PR #17**: KCI v2 — protects against compromised DH keys
- **2026-05-12 PR #22**: CLI HELLO now includes `protocol_version` (closed inconsistency exposed by the downgrade gate itself)

## Links

- [[00-VISION]]
- [[L0-foundation]]
- [[L2-network]]
- [[L5-reputation]]
- [[../PROGRESS]]
