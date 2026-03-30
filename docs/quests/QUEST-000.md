# QUEST-000 — First Contact

> *Every journey begins with a single message to the bus.*

**Realm**: 1 — Foundation
**Difficulty**: Beginner (no programming required for Door 1)
**Time**: 15-30 minutes
**Reward**: Realm 1 access, first XP, clan identity established

---

## Overview

QUEST-000 is the universal entry point to HERMES. Every human starts here — regardless of background, skills, or goals. It has three doors: choose the one that feels natural. All three lead to the same place: your first message on the bus, your first response, and the realization that you can coordinate AI agents with nothing but text files.

---

## Choose Your Door

### Door 1 — The Explorer

*"I want to see what this is before I commit."*

**For**: Curious people. No programming needed. You'll use the command line, but we'll show you exactly what to type.

**Steps**:

1. **Open a terminal** (Mac: Terminal.app, Windows: PowerShell, Linux: any terminal)

2. **Create your first bus file**:
   ```bash
   mkdir -p ~/my-hermes
   cd ~/my-hermes
   ```

3. **Write your first message** — just copy and paste this:
   ```bash
   echo '{"ts":"2026-01-01","src":"me","dst":"*","type":"event","msg":"Hello, HERMES. I am here.","ttl":30,"ack":[]}' > bus.jsonl
   ```

4. **Read it back**:
   ```bash
   cat bus.jsonl
   ```
   You just wrote and read a HERMES message. That's the entire protocol at its core — a line of JSON in a file. No server. No account. No API key.

5. **Add a second message** — this time, make it yours:
   ```bash
   echo '{"ts":"2026-01-01","src":"me","dst":"*","type":"state","msg":"My first quest. I chose to explore.","ttl":30,"ack":[]}' >> bus.jsonl
   ```

6. **Reflect**: Open `bus.jsonl` in any text editor. You can read every message. You can verify every field. Nothing is hidden. This is what sovereignty looks like.

**You completed Door 1 when**: You have a `bus.jsonl` with at least 2 messages you wrote yourself.

---

### Door 2 — The Builder

*"I want to install the real thing and make it work."*

**For**: Developers, engineers, people comfortable with Python/CLI.

**Steps**:

1. **Install HERMES**:
   ```bash
   cd /tmp
   git clone https://github.com/dereyesm/hermes.git
   cd hermes/reference/python
   pip install -e .
   ```

2. **Initialize your clan**:
   ```bash
   hermes install --clan-id my-clan --display-name "My First Clan"
   ```
   This creates `~/.hermes/` with your config, generates cryptographic keys (Ed25519 + X25519), and sets up the agent daemon.

3. **Write a message using the Python API**:
   ```python
   from hermes.message import create_message
   from hermes.bus import write_message

   msg = create_message(
       src="builder",
       dst="*",
       type="state",
       msg="QUEST-000 complete. Ready to build.",
   )
   write_message("~/.hermes/bus/active.jsonl", msg)
   ```

4. **Verify with the CLI**:
   ```bash
   hermes bus --pending
   ```

5. **Connect to your AI agent**:
   ```bash
   hermes adapt claude-code    # or: hermes adapt opencode / hermes adapt cursor
   ```
   Your AI assistant now reads your HERMES bus. You can coordinate.

**You completed Door 2 when**: `hermes bus --pending` shows messages and `hermes adapt` succeeded for your preferred agent.

---

### Door 3 — The Connector

*"I want to do this with someone else."*

**For**: People who learn by teaching. Pairs, teams, friends.

**Steps**:

1. **Find a partner.** This can be a friend, colleague, or someone from the HERMES community.

2. **Both install HERMES** (follow Door 2, steps 1-2). Each of you gets your own clan.

3. **Exchange public keys**:
   ```bash
   # Person A sends their public key to Person B
   cat ~/.hermes/keys/gateway.pub
   # Person B saves it
   mkdir -p ~/.hermes/keys/peers/
   echo "<Person A's key>" > ~/.hermes/keys/peers/partner.pub
   ```

4. **Send your first cross-clan message**:
   ```bash
   hermes send --to partner --msg "First contact. Can you read this?"
   ```

5. **Receive and acknowledge**:
   ```bash
   hermes bus --pending
   # Read the message, then acknowledge it
   ```

6. **Reflect together**: What did it feel like to communicate through a protocol you can both inspect? No platform in the middle. No algorithm deciding what you see. Just your words, cryptographically signed, on both your machines.

**You completed Door 3 when**: Both partners have sent and received at least one message through the HERMES bus.

---

## After QUEST-000

You are now Realm 1. Here's what's unlocked:

| What | How |
|------|-----|
| **Your namespace** | You have an identity on the HERMES bus |
| **Your first XP** | 10 XP for completing QUEST-000 |
| **QUEST-001 options** | Choose your path: automate a task (Stability), join a clan (Belonging), or create a skill (Mastery) |
| **The reflection prompt** | Before moving on, answer: *"What problem in my life could this help me solve?"* |

### The Reflection (Required)

HERMES does not let you level up without thinking. Before QUEST-001, write one message to your bus:

```bash
echo '{"ts":"2026-01-01","src":"me","dst":"me","type":"event","msg":"What I want to solve: [your answer]","ttl":365,"ack":[]}' >> bus.jsonl
```

This message is for you. TTL 365 — it stays for a year. When you come back to it, you'll see how far you've traveled.

---

## FAQ

**Q: Do I need to know programming?**
A: Door 1 requires zero programming. Door 2 requires basic Python. Door 3 requires basic CLI + a partner.

**Q: Do I need an AI agent?**
A: Not for QUEST-000. The bus works without any AI. But HERMES becomes powerful when you connect an agent (Claude Code, OpenCode, Cursor, or any tool with an adapter).

**Q: What if I fail?**
A: You can't fail QUEST-000. There is no timer, no score, no penalty. If something doesn't work, that's a bug in HERMES, not in you. File an issue — you're already contributing.

**Q: Is my data private?**
A: Your bus lives on YOUR machine. No server sees it unless you choose to connect to a hub. Your keys are yours. `ls -la ~/.hermes/keys/` — you can verify.

---

*"The journey of a thousand quests begins with `echo >> bus.jsonl`."*
