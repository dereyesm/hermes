---
topic: Memory Management
updated: 2026-03-31
---

# Memory Management — Multi-Dimensional Memory System

## The Problem

Claude Code MEMORY.md files grow without bounds. At >180 lines, context injection becomes wasteful. At >200 lines, critical information gets lost in noise. The Clan has 7 dimensions, each with its own MEMORY.md.

## Architecture

### MEMORY.md = Pure Index (since 2026-03-31)
MEMORY.md is an index, NOT a content store. Each entry is 1 line:
```
- [Topic name](topic_file.md) — one-line summary
```

### Topic Files = Content Store
Detailed content lives in `memory/*.md` files. MEMORY.md links to them.
One topic per file. File names use snake_case. Each file has YAML frontmatter:
```yaml
---
name: Human-readable name
description: 1-2 sentence purpose
type: project | feedback | reference | user
---
```

### Decisions Archive
`memory/decisions-archive.md` stores one-liner records of decisions >30 days old.
Format: `- YYYY-MM-DD: [Project] [Decision] [Outcome]`

## Limits

| Metric | Soft Limit | Hard Limit |
|--------|-----------|-----------|
| MEMORY.md lines | 180 | 200 |
| Next Session Prompts per file | 3 | 4 |
| Lines per prompt | 5 | 8 |
| Total prompts section | 15 lines | 20 lines |
| Topic file lines | 100 recommended | No hard limit |

## Enforcement Stack

| Tool | Type | When | Action |
|------|------|------|--------|
| `memory-health-check.sh` | SessionStart hook | Every session | Warns at 180, alerts at 200 |
| Exit protocol Step 3 | Manual | Session close | Forces compaction before writing |
| `memory-audit.sh` | Automation | Weekly (Sundays 9AM) | Full health report, 7 dimensions |
| `compaction-log.md` | Transparency | Each compaction | Dated log of what was moved/purged |

## Compaction Process

1. Count lines of MEMORY.md
2. If > 180: identify inline content > 2 lines
3. Create topic file with frontmatter OR merge into existing topic file
4. Replace inline content with 1-line index entry
5. Purge completed Next Session Prompts
6. Archive decisions > 30 days
7. Log the compaction to `~/.claude/automation/logs/compaction-log.md`
8. Verify final line count < 180

## Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| COMPLETADO blocks in prompts | Purge immediately |
| 48-line prompt blocks | Max 5 lines per prompt |
| Inline SaaS cost tables | Move to topic file |
| Sprint details 2+ sprints ago | Archive |
| Cross-dimension content | Move to correct dimension |
| Zero topic files (all inline) | Extract everything >2 lines |

## Inventory (as of 2026-03-31)

| Dimension | Lines | Topic Files | Status |
|-----------|-------|-------------|--------|
| Global | 159 | 21 | OK |
| Nymyka | 69 | 30 | OK (post-compaction from 227) |
| Dev | 115 | 17 | OK (post-compaction from 189) |
| MomoshoD | 179 | 5 | At limit |
| MomoFinance | 67 | 12 | OK (post-compaction from 187) |
| Zima26 | 152 | 23 | OK |
| HERMES | 151 | 0 | OK (consider topic files) |

## For New Clans

If building a new multi-dimensional system:
1. Start with MEMORY.md as pure index from day 1
2. Create topic files immediately when content exceeds 2 lines
3. Set up `memory-health-check.sh` hook early
4. Run `memory-audit.sh` weekly
5. Never skip compaction logging — your future self needs the trail
