---
topic: Ecosystem Changelog
updated: 2026-03-31
---

# Changelog — Claude Code Ecosystem (Clan Momosho D.)

## 2026-03-31 — Memory Architecture Revision (Consejo Option C)

### New Infrastructure
- `memory-health-check.sh` — SessionStart hook, warns at 180/200 lines
- `memory-audit.sh` — weekly automation, full health report across 7 dims
- `com.momoshod.memory-audit.plist` — launchd weekly Sunday 9 AM
- `compaction-log.md` — transparency log for all compaction actions

### Structural Changes
- MEMORY.md redesigned as PURE INDEX across all dimensions
- Nymyka: 227 -> 69 lines (10 new topic files, 3 merges)
- Dev: 189 -> 115 lines (3 new topic files, 1 merge)
- MomoFinance: 187 -> 67 lines (12 new topic files from scratch)
- 25 new topic files total, zero information loss
- Cross-dimension pollution fixed (HERMES prompt in Dev, Visa in Dev)

### Documentation
- `memory-management.md` added to Claude Sensei KB
- `best-practices.md` updated with Memory Architecture Pattern
- `changelog.md` created (this file)
- `exit-protocol.md` updated with compaction transparency + pure index rules

### Policy Updates
- MEMORY.md = pure index (entries max 1 line, content in topic files)
- Next Session Prompts: max 3 per MEMORY.md, max 5 lines each
- COMPLETADO blocks must be purged immediately
- Every compaction leaves trace in compaction-log.md

## 2026-03-28 — Claude Sensei KB Evolution + Memory Backup Agent
- KB grew from 4 to 8 files (hermes-integration.md closed the gap)
- Arena BR scored 3.85/5 (77 XP)
- memory-backup.sh integrated as exit-protocol Step 4.5
- clan-memory repo as GitHub backup destination

## 2026-03-25 — Supply Chain Audit (MULTI-018)
- LiteLLM/TeamPCP compromise verified — Clan CLEAN
- ~/.secrets/ permissions 644->600 FIXED
- supply-chain-sop.md created
- SOP integrated into rules/

## 2026-03-23 — Date Context Hook
- date-context.sh injects [DATE] day-of-week into every prompt
- Prevents LLM day-of-week inference failures
- 9 files updated for Paso 0 compliance

## 2026-03-17 — Bus Hygiene
- hermes-pull.sh v2: cursor/dim + pull-is-ACK + auto-sweep TTL
- bus.jsonl: 209 -> 44 messages (165 archived)
- Circular dependency broken (sweep no longer depends on exit-protocol)
