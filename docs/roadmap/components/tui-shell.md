---
title: TUI Shell — amaru shell (master control board)
type: component
status: planned
percent: 0
layer: L3-experience
priority: P0
depends_on: ["[[../layers/L2-network]]"]
---

# `amaru shell` — Master Control Board

The single piece that makes the metaverse **feel real**. Not a CLI — a **tablero**.

## Vision (refined 2026-05-12)

`amaru shell` is a **gamified master control board** with switchable **views** and **per-dimension scoping**, fully **personalizable**. The default view is a **pedagogical global dashboard** simple enough that someone new can read it; advanced users switch to richer views.

```
amaru shell                          # default: global pedagogical view
amaru shell --view wow               # World-of-Warcraft style (clans=guilds, quests=raids)
amaru shell --view gta               # GTA-Online style (open-world economy, missions)
amaru shell --view executive         # minimalist (KPIs, sparklines, terse)
amaru shell --view personal          # only your personal-dimension state
amaru shell --view profesional       # only your work-dimension state
amaru shell --view artistica         # only your creative-dimension state
amaru shell --view custom            # user-defined layout
```

## The four canonical views

See [[shell-views]] for the detailed mocks. Quick summary:

| View | Audience | Density | Metaphor |
|---|---|---|---|
| **global** | newcomers | low | pedagogical dashboard, big labels |
| **wow** | gamers, social users | high | guild roster, quest log, raid finder |
| **gta** | makers, hustlers | high | open-world map, missions list, economy panel |
| **executive** | operators, decision-makers | medium | KPI strip, sparklines, terse status |
| **dimension-scoped** (personal / profesional / artistica / etc.) | focused work | medium | only one dimension visible, others muted |
| **custom** | power users | varies | YAML-defined panes |

All views share the same **data substrate** (bus, roster, quests, Welt, mood). Only presentation differs.

## Pedagogical global view (default — for someone new)

```
┌─ Amaru — your map of the network ──────────────────────────────────────────┐
│                                                                            │
│   You are: momoshod  •  Welt: Amaru (mythical, lvl 521)  •  152d streak    │
│                                                                            │
│   Your dimensions          Clans you can reach          Open invitations   │
│   ────────────────         ──────────────────────        ──────────────     │
│   personal   ●             jei        ● online           (none)            │
│   profesional●             nymyka     ○ offline                            │
│   artistica  ○             tinkuy     ○ offline                            │
│                                                                            │
│   What you can do now                                                      │
│   ───────────────────                                                      │
│   • /quest browse    see what others need help with                        │
│   • /quest publish   ask the network for help                              │
│   • /agent invoke    open Claude / Gemini / Continue here                  │
│   • /view wow        try a more detailed view                              │
│                                                                            │
│   What is Amaru? (press ?)                                                 │
└────────────────────────────────────────────────────────────────────────────┘
```

Big labels, few panels, no jargon. The first time someone opens `amaru shell` they should understand what it is in 10 seconds.

## Per-dimension scoping

Every Amaru user has multiple dimensions (personal, profesional, artistica, comunitaria, etc.). The shell can **scope** to a single dimension:

```
amaru shell --view dimension:artistica
```

Shows only:
- Welt form for that dimension
- Clans and quests tagged with that dimension
- Bus stream filtered by that dimension
- Suggested agents for that dimension

This protects against context overload — you don't need to see your tax obligations while you're writing poetry.

## Personalization

Each user has `~/.amaru/shell-config.yaml`:

```yaml
default_view: global
custom_views:
  morning:
    panes:
      - type: welt
        position: top-left
      - type: today_quests
        position: top-right
      - type: bus_stream
        position: bottom
        filter: "type:dispatch OR type:event"
      - type: pomodoro
        position: top-center
  evening:
    panes:
      - type: bus_stream
        filter: "today's activity"
      - type: gratitude_prompt
```

Layouts are composable. Power users can share their YAML configs (`amaru shell config publish`) and others can adopt them (`amaru shell config adopt <user>/morning`).

## Slash commands MVP (any view)

| Command | Action |
|---|---|
| `/send <clan> <msg>` | invokes `amaru send` |
| `/inbox` | reads `amaru inbox` |
| `/quest publish` | opens form, publishes to bus |
| `/quest accept <id>` | accepts a quest |
| `/agent invoke claude` | starts Claude Code session attached to clan context |
| `/agent invoke gemini` | starts Gemini CLI |
| `/agent invoke continue` | starts Continue.dev |
| `/peer invite` | generates invite link |
| `/welt` | full Welt sprite + history |
| `/view <name>` | switch view |
| `/dimension <name>` | scope to one dimension |
| `/help` | help |
| `/quit` | exit |

## Stack

**Python + textual** — Daniel's primary stack. Textual supports:
- Composable widgets
- Reactive data binding (perfect for live bus streams)
- CSS-like theming (per view)
- Async (matches Amaru's WebSocket model)

## Spec target

**AES-7531 — Immersive Shell**

Sections:
1. Layout protocol (pane grammar, focus model)
2. View definitions (global, wow, gta, executive, dimension-scoped, custom)
3. Slash command grammar
4. Bus stream filter rules
5. Welt + mood UI binding
6. Adapter handshake (how `/agent invoke X` boots adapter X)
7. Personalization (shell-config.yaml schema)
8. Sharing layouts (publish/adopt)
9. Accessibility (screen reader, color blindness, terminal width fallbacks)

## Risks

- **Scope creep**: easy to want every feature in v1. Defend MVP boundary (global view + wow view + basic slash commands).
- **TUI is not for everyone**: Windows users, GUI lovers. Mitigation: keep imperative CLI working forever.
- **View proliferation**: one canonical view per metaphor; community can fork.

## Links

- [[../00-VISION]]
- [[../layers/L3-experience]]
- [[shell-views]]
- [[constitution]]
- [[quest-board]]
- [[../PROGRESS]]
