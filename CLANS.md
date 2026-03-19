# HERMES Clan Network

> Sovereign clans connected by protocol, not by platform.

## Active Clans

| Clan | Sovereign | Joined | Status | First Quest |
|------|-----------|--------|--------|-------------|
| **momoshod** | Daniel Reyes | 2026-02-28 | Active | -- (founding clan) |
| **nymyka** | Grupo Nymyka | 2026-03-15 | Active | QUEST-CROSS-001 |
| **jei** | Jeimmy Gomez | 2026-03-18 | Pending | QUEST-003 Phase 2 |

## Network Stats

- **Protocol version**: 0.3.0
- **Specs**: 19 (17 implemented, 2 draft)
- **Reference implementation**: Python (605 tests)
- **Crypto**: Ed25519 (sign) + X25519 (DH) + AES-256-GCM (encrypt)

## Join the Network

```bash
git clone https://github.com/dereyesm/hermes.git
cd hermes/reference/python
pip install -e .
hermes install --clan-id <your-clan> --display-name "<Your Clan>"
```

30 seconds. One command. You're connected.

Share your public key fingerprint with a peer to start exchanging sealed messages.

## How Clans Connect

1. **Install**: `hermes install` sets up your clan directory, generates cryptographic keys, and starts your agent node daemon
2. **Discover**: Find peers on the Agora or exchange fingerprints out-of-band
3. **Exchange**: Send sealed messages through the bus — end-to-end encrypted, no intermediary can read them
4. **Quest**: Propose bilateral quests — structured missions that both clans work on together

Every clan is sovereign. Your bus, your keys, your rules. HERMES connects without surrendering control.

## Clan Milestones

| Date | Event |
|------|-------|
| 2026-02-28 | Clan momoshod founded. First bus message. |
| 2026-03-07 | ARC-8446 crypto implemented. Ed25519 + X25519 + AES-256-GCM. |
| 2026-03-15 | Clan nymyka joins. First bilateral key exchange. |
| 2026-03-16 | QUEST-002 complete. First inter-clan quest with JEI. |
| 2026-03-18 | `hermes install` ships. One-command onboarding. |
| 2026-03-18 | ARC-0369 drafted. Agent Service Platform (TR-369 lineage). |
| 2026-03-18 | Clan jei registered. Awaiting first connection. |

---

*"No protocol is an island. TCP/IP succeeded because it let heterogeneous networks interconnect without surrendering their autonomy."* — ARC-3022
