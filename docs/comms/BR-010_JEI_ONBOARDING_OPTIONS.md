# BR-010 — JEI Onboarding Experience Design

> hermes-community | 2026-03-18
> Audience: internal (Daniel + JEI onboarding decision)

---

## Context

JEI has bilateral crypto keys with DANI (QUEST-003 Phase 1 COMPLETE).
She has Claude Code. She's on Mac (arm64). QUEST-003 Phase 2 is March 22.
The goal: she runs one command and Daniel is already there, waiting.

---

## Option A — Quest-Based (relay dispatch)

### How it works

Daniel writes a HERMES quest message to the relay before March 22.
When JEI opens her Claude Code session that morning, the SYN hook picks
it up. Huitaca surfaces it in Quest Board format. She doesn't get an
email — she gets a **mission**.

### Relay message (append to `dani_outbox.jsonl`)

```json
{"ts":"2026-03-22","src":"dani","dst":"jei","type":"quest","msg":"QUEST-003 Phase 2: You are cleared for live connection. Install HERMES on your machine in 3 commands. DANI agent node is running and listening for your handshake. Instructions: https://github.com/dereyesm/hermes/blob/main/docs/GETTING-STARTED.md#install — Expected: fingerprint exchange + bilateral ECDHE ping. Timeline: today.","ttl":3,"ack":[]}
```

### What JEI sees (Quest Board, via Huitaca)

```
QUEST-003 Phase 2 — Active Mission
From: Clan DANI | Priority: high | Expires: 3 days

You are cleared for live connection.
DANI agent node is already running, listening for your handshake.

Step 1: pip install hermes-protocol
Step 2: hermes install --clan-id jei --display-name "Clan JEI"
Step 3: hermes status   ← confirm you're online

Then: send your fingerprint. DANI will complete the bilateral ECDHE
exchange and you'll receive a sealed test message within minutes.
```

### Step-by-step flow (A)

1. Daniel pushes relay message night of March 21.
2. March 22 morning: Huitaca surfaces quest on JEI's session start.
3. JEI runs 3 commands. Installer runs in ~30 seconds.
4. On JEI's Mac: desktop notification fires — *"Agent Node running. You're connected as jei!"*
5. Her daemon starts polling. Her first `hermes status` shows `peers: []`.
6. JEI sends fingerprint to Daniel (relay or direct).
7. Daniel runs `hermes peer add jei` — JEI's status flips to `peers: [dani]`.
8. Daniel's daemon detects new peer registration → **desktop notification fires on Daniel's Mac**.
9. Daniel sends a sealed ECDHE message via relay.
10. JEI's daemon receives it, decrypts, surfaces via Huitaca.

### The "uala" moment (Option A)

Daniel's Mac plays the Glass sound chime (macOS `osascript` with
`sound name "Glass"`) the instant JEI's peer registration propagates.
He was already there. She connected. The network found him.

---

## Option B — Email/Direct

### Message draft

**Subject**: HERMES is ready for you — 3 commands

---

Jeimmy,

Phase 1 is done. Your keys are valid. My agent node is already running
and listening for your handshake.

Run this on your Mac:

```bash
pip install hermes-protocol
hermes install --clan-id jei --display-name "Clan JEI"
hermes status
```

That's it. ~30 seconds.

When `hermes install` finishes, you'll get a desktop notification:
*"Agent Node running. You're connected as jei!"*

Then send me your key fingerprint (shown during install) so I can add
you as a peer. I'll confirm with a sealed ECDHE message — that's
Phase 2 live.

See you on the other side.

— Daniel (Clan DANI)

---

### What JEI sees when `hermes install` runs

```
  ╔══════════════════════════════════════╗
  ║  H E R M E S   I N S T A L L        ║
  ╚══════════════════════════════════════╝

  Platform: macos (arm64)
  Clan dir: /Users/jeimmy/.hermes

  [OK] Clan initialized at /Users/jeimmy/.hermes
  [OK] Ed25519 + X25519 keys generated
       Fingerprint: 65bf:b893:...
  [OK] agent_node section added to gateway.json
  [OK] LaunchAgent installed (survives reboot)
  [OK] Claude Code hooks installed (3 hooks)
  [OK] Agent Node started (PID 48291)

  You're connected! Run 'hermes status' to check.
  Share your public key fingerprint with peers to start exchanging.
```

Desktop notification (macOS Glass chime):
> HERMES — Agent Node running. You're connected as jei!

### Step-by-step flow (B)

1. Daniel sends email. JEI runs 3 commands.
2. Install completes. Desktop notification fires on JEI's Mac.
3. JEI replies with fingerprint.
4. Daniel adds JEI as peer. Daniel's Mac fires notification.
5. Daniel sends sealed ECDHE test message via relay.
6. JEI opens it: `hermes inbox`. Phase 2 complete.

### The "uala" moment (Option B)

Same Glass chime on Daniel's side. The difference from Option A: here
JEI is actively following instructions and expects it. Option B is
*functional*. Option A is *a mission she walks into*.

---

## Comparison

| | Option A (Quest) | Option B (Email) |
|---|---|---|
| JEI experience | "I have a mission" | "I have instructions" |
| Surprise factor | High — Huitaca surfaces it without email | None |
| Friction for Daniel | Write relay message night before | Write one short email |
| Requires Huitaca working | Yes | No |
| Recovery if Huitaca misses it | Send email as fallback | Already email |
| "uala" on Daniel's side | Identical (Glass chime on peer connect) | Identical |
| Recommended for March 22 | Yes, if relay is stable | Yes, as fallback |

---

## What needs to be ready before sending (either option)

1. QUEST-003 Phase 2 commit pushed (bus.py + message.py + test_bus.py — currently pending).
2. Daniel's daemon running: `hermes daemon start` (or LaunchAgent loaded).
3. JEI's fingerprints pre-loaded in Daniel's gateway as a pending peer
   entry — so her connection auto-completes when she appears.
4. Relay channel JEI-HERMES-011 stable.
5. `pip install hermes-protocol` works from JEI's machine OR she clones
   the repo and installs from source (confirm which before sending).

---

## Recommendation

**Send Option A relay message March 21 night. Include Option B email
as the same-day backup if Huitaca doesn't surface the quest by noon.**

The "uala" is identical in both paths — it lives in `send_notification()`
in `installer.py` on JEI's side, and in the peer-registration event
handler on Daniel's. That moment doesn't depend on which option gets
her there.
