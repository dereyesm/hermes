---
title: Shell Views — canonical layouts
type: component
status: planned
percent: 0
layer: L3-experience
priority: P0
depends_on: ["[[tui-shell]]"]
---

# Shell Views — canonical layouts

Concrete mocks for each canonical view of [[tui-shell]]. Each view is **the same data**, **different presentation**.

## 1. Global (default — pedagogical)

```
┌─ Amaru — your map of the network ──────────────────────────────────────────┐
│   You are: momoshod  •  Welt: Amaru mythical lvl 521  •  152d streak       │
│                                                                            │
│   Dimensions       Clans reachable          Open invitations               │
│   personal   ●     jei        ● online      (none)                         │
│   profesional●     nymyka     ○ offline                                    │
│   artistica  ○     tinkuy     ○ offline                                    │
│                                                                            │
│   What you can do now                                                      │
│   /quest browse  /quest publish  /agent invoke  /view wow                  │
│                                                                            │
│   What is Amaru? (press ?)                                                 │
└────────────────────────────────────────────────────────────────────────────┘
```

For: someone opening Amaru for the first time. Goal: 10-second comprehension.

---

## 2. WoW (guild + raid + quest log)

```
┌─ Amaru ─ momoshod ─────────────── [Realm: clan-network] ─ XP:26000 lvl:521 ┐
├─ Guild roster ──────────────┬─ Quest log ─────────────────────────────────┤
│ [GM] momoshod      ready    │ [Q] QC002 Phase 1 bilateral cut    DONE ✅  │
│      jei           ready    │ [Q] Issue #18 follow-up smoke E2E  open     │
│      nymyka        offline  │ [Q] AES-7531 TUI shell draft       open     │
│      tinkuy        offline  │ [Q] cooking-translator (jei)       open     │
├─ Party (active session) ────┴─ Combat log (last 10 bus msgs) ──────────────┤
│ momoshod (You) — Amaru form │ 15:58 jei → momoshod  receipt-ok            │
│ jei                         │ 15:54 momoshod → jei  QC002-T4              │
│                             │ 15:52 jei → momoshod  hello                 │
│                             │ ...                                         │
├─ LFG status: READY ─────────┴─ Tells: 0 unread ────────────────────────────┤
│  q quit  /  cmd   tab pane   ↑↓ select   enter act                         │
└────────────────────────────────────────────────────────────────────────────┘
```

For: social users, gamers, people who think in parties/guilds/raids.

Metaphors: clan = guild, quest = raid, bus stream = combat log, hub roster = guild roster, ready/busy = LFG status, tells (whispers) = direct messages.

---

## 3. GTA (open-world map + missions + economy)

```
┌─ Amaru Online ─ Lobby: clan-network ─────────────────────── $REP 4,732 ────┐
├─ Network map (active hubs) ─────────┬─ Missions ──────────────────────────┤
│       jei ●                         │  Cooking translator     ★★★          │
│        │  S2S                       │   "Help translate Quechua recipes"   │
│       you ●                         │   Pay: signed thank-you              │
│        │                            │   Time: 2h     Distance: 1 hop       │
│   nymyka ○      tinkuy ○            │   [accept]                           │
│                                     │                                      │
│  ↑↓ pan  +/- zoom  enter focus      │  Python tutor for beginner   ★       │
├─ Recent activity ───────────────────┤   Reward: reciprocity (graphic dsgn) │
│ ◆ Bilateral cut completed (12 may)  │   Time: open    Distance: 2 hops     │
│ ◆ v0.6.0a1 release shipped          │   [accept]                           │
│ ◆ Issue #13 closed                  │                                      │
├─ Garage (your agents) ──────────────┴─ Stats ───────────────────────────────┤
│ Claude Code      ready              │ Quests completed: 47                  │
│ Gemini CLI       ready              │ Endorsements: 3 trusted clans         │
│ Continue.dev     ready              │ Constitutional violations: 0          │
└─────────────────────────────────────┴───────────────────────────────────────┘
```

For: makers, freelancers, hustlers, people who think in missions/economy/reputation.

Metaphors: hub = lobby, quest = mission, agent stack = garage, reputation = $REP, federation graph = open-world map.

---

## 4. Executive (minimalist KPIs)

```
amaru :: momoshod :: 2026-05-12 15:58 COT

  network        ████████████████ 4/4 peers   • jei reachable  • s2s up
  bus            ████████░░░░░░░░ 2.4k msgs   • 7d trend ↗
  quests         open: 3  •  active: 0  •  closed today: 1 (Issue #13)
  reputation     trusted (3 endorsements)
  Welt           Amaru mythical lvl 521 streak 152d mood: energized

  recent commits
    aa2c2ff fix(cli): amaru send HELLO protocol_version
    6675835 feat(qc002): bilateral 12-may (JEI merge)

  next decision (P0)
    AES-7531 TUI shell — draft or defer until Patricio onboarded?
```

For: operators, time-pressed decision-makers, status-only checks.

Dense, terse, sparkline-friendly. No metaphor — just signal.

---

## 5. Dimension-scoped (e.g. `--view dimension:artistica`)

```
┌─ Amaru — artistica only ───────────────────────────────────────────────────┐
│   Welt: Quetzalcóatl (MomoshoD)                                            │
│   "la palabra crea mundos — viento que nombra las cosas"                   │
│                                                                            │
│   Current writing                                                          │
│   • "Ciclo 1 editorial completo — IE→Arbol→Nakama→Gear5 (4 published)"    │
│   • Next: IE #2                                                            │
│                                                                            │
│   Clans in this dimension                                                  │
│   tinkuy-collective   ○                                                    │
│   eltercerojo         ○                                                    │
│                                                                            │
│   Recent bus (artistica filter)                                            │
│   • 04-09 Beca Minciencias 975 UNAD — pending submit pre-17                │
│   • 04-06 Pitch Miguel Riano post-NYC                                      │
└────────────────────────────────────────────────────────────────────────────┘
```

For: focused work. When writing, finance shouldn't be visible.

Available dimension scopes (per Daniel's setup): `personal`, `profesional`, `artistica`, `comunitaria`, `financiera`, `vivienda`, `amaru`. Each clan defines its own list.

---

## 6. Custom (user-defined YAML)

User writes `~/.amaru/shell-config.yaml`:

```yaml
default_view: morning
custom_views:
  morning:
    title: "Buen día — 06:00"
    panes:
      - type: welt
        position: top-left
        size: 30%
      - type: today_quests
        position: top-right
        size: 70%
      - type: bus_stream
        position: bottom
        size: 60%
        filter: "type:dispatch"
      - type: pomodoro
        position: top-center
        size: 20%
  retro:
    title: "Cierre de sesión"
    panes:
      - type: bus_stream
        filter: "today's events"
      - type: prompt
        question: "Qué aprendiste hoy?"
        save_to: "~/.amaru/sessions/$(date).md"
```

Then `amaru shell --view morning` boots the morning layout.

**Sharable**: `amaru shell config publish morning` writes the YAML to bus as a public quest; anyone can adopt via `amaru shell config adopt <peer>/morning`.

---

## Common substrate

All views read from the **same** data sources. The view is *only* a presentation contract:

| Data source | Provided by |
|---|---|
| Welt state | `~/.claude/welt-state.json` + sprites |
| Bus stream | `~/.amaru/bus.jsonl` |
| Hub roster | `amaru hub roster` |
| Quests | extends `amaru quest browse` (see [[quest-board]]) |
| Reputation | local computation (see [[reputation]]) |
| Dimensions | parsed from clan's `CLAUDE.md` firewall table |

Implementing a new view = mapping these sources to panes. No new protocol logic required.

## Links

- [[tui-shell]]
- [[../layers/L3-experience]]
- [[../00-VISION]]
