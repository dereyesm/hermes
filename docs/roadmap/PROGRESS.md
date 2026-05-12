---
title: Progress Tracker
type: tracker
---

# Progress Tracker

> Update this table whenever a node moves. See [[00-VISION]] for context.

## Overall: 60% of foundation, 0% of experience/governance

```
[█████████████████████████████░░░░░░░░░░░░░░░░░░░] 60%  Foundation layers (L0-L2)
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  0%  Experience layer (L3)
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  0%  Governance layer (L4)
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  0%  Reputation layer (L5)
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  0%  Marketplace layer (L6)
```

## By layer

| Layer | Component | Status | % | Specs / Code |
|---|---|---|---|---|
| L0 Foundation | Bus message format | live | 100 | ARC-5322 |
| L0 Foundation | Hub server | live | 100 | ARC-4601 §15 |
| L0 Foundation | Wire protocol | live | 100 | `docs/wire-protocol-hub.md` |
| L1 Identity | Ed25519 signatures | live | 100 | ARC-8446 |
| L1 Identity | X25519 ECDHE | live | 100 | ARC-8446 |
| L1 Identity | KCI v2 identity binding | live | 100 | ARC-8446 §4.4 (PR #17) |
| L1 Identity | Downgrade protection | live | 100 | ARC-4601 §15.1 (PR #15) |
| L2 Network | S2S federation | live | 100 | ARC-4601 §17 |
| L2 Network | Peer discovery (Agora) | live | 100 | `amaru/agora.py` |
| L2 Network | Auto-peer TOFU | live | 100 | ARC-0370 |
| L2 Network | A2A/MCP bridge | live | 100 | ARC-7231 |
| L2 Network | Quest dispatch (Dojo) | live | 100 | ARC-2314 |
| L3 Experience | [[components/tui-shell]] — `amaru shell` | planned | 0 | AES-7531 *(to draft)* |
| L3 Experience | Welt integration | live | 50 | already exists, needs UI binding |
| L3 Experience | Multi-LLM in-shell | live | 50 | adapters exist, needs UX |
| L4 Governance | [[components/constitution]] — ATR-CONST-01 | planned | 0 | *to draft* |
| L4 Governance | Consequence engine | planned | 0 | *to draft* |
| L5 Reputation | [[components/reputation]] — ATR-REP-01 | planned | 0 | *to draft* |
| L5 Reputation | Quest receipts as proof | live | 30 | ATR-Q.931 §8 receipts exist |
| L6 Marketplace | [[components/quest-board]] — public quest publish/subscribe | planned | 0 | *to draft (extend ARC-2314)* |
| L6 Marketplace | Bidding / escrow | planned | 0 | *to draft* |

## Quick wins (next 30 days)

- [ ] Draft AES-7531 (TUI shell spec) — [[components/tui-shell]]
- [ ] Prototype `amaru shell` MVP with `textual` library
- [ ] Show prototype to JEI + Patricio for feedback
- [ ] Decide governance model: voluntary vs enforced (see [[principles/constitution]])

## Long arc (6-12 months)

- L3 Experience: working immersive shell
- L4 Governance: constitution v1 ratified by ≥3 clans
- L5 Reputation: trust score computed from bus history
- L6 Marketplace: first public quest published + accepted by external clan
- Then: invite Patricio's FlowForgers + other Latin-American collectives
