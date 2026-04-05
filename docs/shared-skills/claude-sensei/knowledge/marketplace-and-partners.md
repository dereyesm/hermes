---
topic: Skills Marketplace & Partner Network
updated: 2026-03-25
---

# Skills Marketplace

## How It Works
- Official repo: github.com/anthropics/skills (Apache 2.0)
- Install: `/plugin marketplace add anthropics/skills`
- Per-skill: `/plugin install skill-name@anthropic-agent-skills`
- Claude.ai has built-in Skills UI (Personalizar > Skills)
- Categories: Productivity, Engineering, Finance, Legal, Marketing, Sales, Customer Support, Brand voice

## Creating a Publishable Skill

Minimum: folder + SKILL.md with frontmatter (name, description).
Submit via PR to anthropics/skills repo.

## Skill Structure for Marketplace

```
my-skill/
├── SKILL.md          (required — frontmatter + instructions)
├── template.md       (optional — output templates)
├── examples/         (optional — usage examples)
└── scripts/          (optional — helper scripts)
```

## Plugin Structure (bundles multiple skills)

```
my-plugin/
├── plugin.md         (required — metadata)
├── skills/           (slash commands)
├── commands/         (.md custom commands)
├── hooks/            (hook configurations)
├── agents/           (agent definitions)
└── README.md         (marketplace listing)
```

## Marketplace Opportunity for Nymyka

33 skills built in-house = proven methodology. The marketplace is the distribution channel for a **skill factory** business model (see `skill-factory-vision.md`).

---

# Claude Partner Network

## Overview
- $100M investment for 2026
- Free membership, apply at claude.com/partners
- For organizations delivering AI solutions with Claude

## Benefits
- Partner Portal: Academy training, sales playbooks, co-marketing
- Technical support: Applied AI engineers on live deals
- Services Partner Directory listing
- Priority CCA-F certification access
- Co-selling support

## CCA-F (Claude Certified Architect, Foundations)

| Campo | Detalle |
|-------|---------|
| Costo | $99/intento |
| Preguntas | 60, proctored (browser + webcam) |
| Passing score | 720/1000 |
| Acceso gratis | Via Partner Network (primeros 5,000) |

### 5 Dominios del Examen

| Dominio | Peso |
|---------|------|
| Agentic Architecture & Multi-Agent Design | 27% |
| Claude Code Configuration & Workflow Automation | 20% |
| Advanced Prompt Engineering | 20% |
| Tool Design & MCP Integration | 18% |
| Context Management & Memory Systems | 15% |

Additional certs rolling out through 2026.

## Nymyka Partner Status

| Campo | Estado |
|-------|--------|
| Applied | 2026-03-23 (Consultancy, RAG + Agentic AI) |
| Review | 2-3 semanas estimado |
| Daniel Academy progress | 3/7 cursos completados |
| CCA-F plan | Primera semana Abr 2026 |

## Key Dates

- Partner review: ~Abr 6-13
- CCA-F attempt: primera semana Abr
- Additional certs: rolling out 2026
