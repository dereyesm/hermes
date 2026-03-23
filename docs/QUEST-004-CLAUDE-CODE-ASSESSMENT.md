# QUEST-004: Claude Code Best Practices Assessment

> Cross-clan bilateral quest for auditing and improving Claude Code adoption.

## Overview

| Field | Value |
|-------|-------|
| **Quest ID** | QUEST-004 |
| **Type** | Cross-Quest (bilateral) |
| **Proposer** | Clan DANI |
| **Participants** | Clan DANI, Clan JEI |
| **Spec Basis** | Anthropic Claude Code official documentation |
| **Status** | **COMPLETE** (bilateral scores exchanged 2026-03-22) |
| **Created** | 2026-03-18 |

## Objective

Create a replicable, scored assessment of Claude Code best practices adoption.
Any clan running HERMES can execute this quest independently, compare scores
via relay, and identify gaps to close.

The assessment covers 14 categories and 43 auditable items derived from
Anthropic's official Claude Code documentation.

## Phases

| Phase | Target | Deliverable | Status |
|-------|--------|-------------|--------|
| 1 | 2026-03-18 | Checklist + DANI self-assessment | **DONE** |
| 2 | 2026-03-22 | JEI self-assessment + bilateral comparison | **DONE** (JEI-HERMES-017) |
| 3 | 2026-03-24 | Dashboard widget + gap remediation plan | PENDING |

---

## Assessment Checklist (v1.0)

### Scoring

- **Y** = Implemented
- **P** = Partial / In Progress
- **N** = Not Implemented
- **NA** = Not Applicable

**Score** = Y items / (Total - NA items) x 100

---

### C1. CLAUDE.md & Project Instructions (5 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 1.1 | Global CLAUDE.md | `~/.claude/CLAUDE.md` exists with cross-project preferences | Y |
| 1.2 | Project CLAUDE.md | `./CLAUDE.md` per project with team/dimension instructions | Y |
| 1.3 | Rules directory | `.claude/rules/*.md` modular rules, one topic per file | Y |
| 1.4 | Path-scoped rules | Rules with YAML `paths:` frontmatter for file-pattern scoping | N |
| 1.5 | CLAUDE.md under 200 lines | Main file concise, details delegated to rules/imports | Y |

### C2. Auto Memory & MEMORY.md (4 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 2.1 | Auto memory enabled | Memory system active, files at `~/.claude/projects/<proj>/memory/` | Y |
| 2.2 | MEMORY.md index | Index file under 200 lines, links to topic files | Y |
| 2.3 | Memory topic files | Separate `.md` files by topic, frontmatter with name/type | Y |
| 2.4 | Memory types used | Uses user, feedback, project, reference types appropriately | Y |

### C3. Skills (5 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 3.1 | Skill directory structure | Skills at `~/.claude/skills/<name>/SKILL.md` or project-level | Y |
| 3.2 | SKILL.md frontmatter | Name, description, allowed-tools, model, user-invocable | Y |
| 3.3 | Argument substitution | Uses `$ARGUMENTS`, `$0`, `${CLAUDE_SKILL_DIR}` | P |
| 3.4 | Supporting files | Reference docs, templates alongside SKILL.md | Y |
| 3.5 | Invocation control | `disable-model-invocation` / `user-invocable` configured | Y |

### C4. Subagents (6 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 4.1 | Agent directory | Agents at `~/.claude/agents/<name>/` | Y |
| 4.2 | Agent markdown file | `.md` with YAML frontmatter + system prompt body | Y |
| 4.3 | Frontmatter fields | name, description, tools, model, permissionMode, etc. | Y |
| 4.4 | Persistent memory | `memory: user` or `memory: project` for cross-session learning | Y |
| 4.5 | Worktree isolation | `isolation: worktree` for agents that modify code | N |
| 4.6 | Agent invocation | Natural language triggers or explicit `@agent-name` | Y |

### C5. Hooks (6 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 5.1 | Hook config file | Hooks in `~/.claude/settings.json` or project settings | Y |
| 5.2 | Event coverage | Hooks on Stop, UserPromptSubmit, SessionEnd (and others) | Y |
| 5.3 | Matcher patterns | Regex matchers to scope hooks to specific tools/events | P |
| 5.4 | Exit code handling | Scripts return 0 (allow) or 2 (block) appropriately | P |
| 5.5 | Scripts executable | Hook scripts at known paths, `chmod +x` | Y |
| 5.6 | Hook types | Uses `command` type (shell scripts) | Y |

### C6. Settings & Permissions (7 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 6.1 | Settings hierarchy | Global + project + local settings files | Y |
| 6.2 | Permission rules | `allow` and `deny` arrays with tool patterns | Y |
| 6.3 | Permission mode | Default mode configured (plan/default/etc.) | Y |
| 6.4 | Sandbox config | Sandbox enabled with path prefixes | N |
| 6.5 | Env vars managed | Project env vars in settings `env` section | Y |
| 6.6 | Model pinned | Default model set per project or globally | Y |
| 6.7 | File exclusions | Sensitive files excluded via deny rules or excludes | Y |

### C7. MCP Servers (6 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 7.1 | MCP config file | Servers in `.mcp.json` or `~/.claude.json` | Y |
| 7.2 | Scope isolation | Servers scoped per dimension (project deny rules) | Y |
| 7.3 | Transport types | Correct transport per server (stdio/http) | Y |
| 7.4 | Env var secrets | API keys via env expansion, not hardcoded | Y |
| 7.5 | Agent MCP scoping | Agents restrict MCP access via frontmatter | P |
| 7.6 | OAuth auth | Authenticated servers configured properly | Y |

### C8. Plan Mode (3 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 8.1 | Plan mode accessible | Can enter via Shift+Tab or `--permission-mode plan` | Y |
| 8.2 | Plan as default | Plan mode set as default permission mode | N |
| 8.3 | Plan mode workflow | Used for multi-file changes, refactors, architecture | Y |

### C9. Worktrees (3 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 9.1 | Worktree isolation | Uses `--worktree` for parallel isolated work | N |
| 9.2 | Worktree branching | Worktree branches from default remote | N |
| 9.3 | Worktree cleanup | `.claude/worktrees/` in `.gitignore`, auto-cleanup | N |

### C10. Git Integration (3 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 10.1 | Commit convention | `type(scope): message` with Co-Authored-By footer | Y |
| 10.2 | PR creation | Uses `gh pr create` with structured body | Y |
| 10.3 | Branch naming | Follows convention (feature/, bugfix/, etc.) | Y |

### C11. Context Management (3 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 11.1 | Checkpointing | Uses `/checkpoint` or rewind for save points | N |
| 11.2 | Auto-compaction | Aware of compaction, manages context proactively | P |
| 11.3 | Subagent delegation | Complex tasks delegated to subagents for context isolation | Y |

### C12. Model & Performance (3 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 12.1 | Fast mode | Knows and uses `/fast` toggle | P |
| 12.2 | Effort level | Uses effort levels (low/medium/high) for task complexity | Y |
| 12.3 | Model selection | Uses haiku for simple tasks, opus for complex | Y |

### C13. Keybindings & IDE (3 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 13.1 | Custom keybindings | `~/.claude/keybindings.json` configured | N |
| 13.2 | IDE integration | VS Code / JetBrains plugin installed | N |
| 13.3 | Status line | Custom status line command configured | Y |

### C14. Session Management (3 items)

| # | Item | Description | DANI |
|---|------|-------------|------|
| 14.1 | Session naming | Sessions named descriptively with `/rename` or `-n` | N |
| 14.2 | Session picker | Proficient with `/resume` picker (preview, search) | P |
| 14.3 | Session logs | Session outcomes logged for retrospective | Y |

---

## DANI Assessment Summary (2026-03-18)

| Category | Y | P | N | NA | Items | Score |
|----------|---|---|---|----|----|-------|
| C1. CLAUDE.md | 4 | 0 | 1 | 0 | 5 | 80% |
| C2. Memory | 4 | 0 | 0 | 0 | 4 | 100% |
| C3. Skills | 4 | 1 | 0 | 0 | 5 | 90% |
| C4. Subagents | 5 | 0 | 1 | 0 | 6 | 83% |
| C5. Hooks | 4 | 2 | 0 | 0 | 6 | 83% |
| C6. Settings | 6 | 0 | 1 | 0 | 7 | 86% |
| C7. MCP | 5 | 1 | 0 | 0 | 6 | 92% |
| C8. Plan Mode | 2 | 0 | 1 | 0 | 3 | 67% |
| C9. Worktrees | 0 | 0 | 3 | 0 | 3 | 0% |
| C10. Git | 3 | 0 | 0 | 0 | 3 | 100% |
| C11. Context | 1 | 1 | 1 | 0 | 3 | 50% |
| C12. Model | 2 | 1 | 0 | 0 | 3 | 83% |
| C13. IDE | 1 | 0 | 2 | 0 | 3 | 33% |
| C14. Sessions | 1 | 1 | 1 | 0 | 3 | 50% |
| **TOTAL** | **42** | **7** | **11** | **0** | **60** | **76%** |

> **Note**: Partial (P) items count as 0.5 for scoring.
> Adjusted score: (42 + 3.5) / 60 = **75.8%** — **Advanced** tier.
> Post-gap-closure improvement: 71% -> 76% (+5pp, 3 gaps closed same session).

### Top Gaps (N items to close)

| Priority | Item | Impact | Effort | Status |
|----------|------|--------|--------|--------|
| ~~HIGH~~ | ~~6.3 Default permission mode~~ | ~~Safety~~ | ~~Low~~ | CLOSED 2026-03-18 |
| HIGH | 1.4 Path-scoped rules | Precision of rule application | Medium | OPEN |
| MED | 9.1-9.3 Worktrees | Parallel work isolation | Low | OPEN |
| MED | 11.1 Checkpointing | Error recovery | Low | OPEN |
| ~~MED~~ | ~~12.2 Effort levels~~ | ~~Performance~~ | ~~Low~~ | CLOSED 2026-03-18 |
| LOW | 6.4 Sandbox | Security hardening | Medium | OPEN |
| ~~LOW~~ | ~~6.6 Model pinning~~ | ~~Consistency~~ | ~~Low~~ | CLOSED 2026-03-18 |
| LOW | 13.1-13.2 IDE/keybindings | Ergonomics | Medium | OPEN |
| LOW | 14.1 Session naming | Organization | Low | OPEN |

---

## JEI Assessment Summary (2026-03-22)

Received via JEI-HERMES-017 (ECDHE-encrypted relay, decrypted by DANI).

| Metric | Value |
|--------|-------|
| **Overall score** | ~54% |
| **Memory (C2)** | 100% |
| **Settings (C6)** | 21% |
| **Worktrees (C9)** | 0% |
| **Improvement focus** | Worktrees + settings depth |

### Bilateral Comparison

| Category | DANI | JEI | Delta |
|----------|------|-----|-------|
| Overall | 76% | ~54% | +22pp |
| Memory | 100% | 100% | 0 |
| Settings | 86% | 21% | +65pp |
| Worktrees | 0% | 0% | 0 |

**Key observations:**
- Memory is the strongest category for both clans (100% each)
- Worktrees is the weakest for both (0% each) — shared gap
- Settings is the biggest divergence (+65pp) — DANI's advantage area
- QUEST-004 closed by JEI as Phase 0 input for QUEST-005

---

## Guide for New Clans

### How to Run This Assessment

1. **Fork/copy this checklist** to your clan's HERMES docs
2. **For each item**, check your local setup:
   - Does the file/config exist?
   - Is it actively used (not just created)?
   - Does it follow the documented pattern?
3. **Score yourself** honestly: Y/P/N/NA
4. **Calculate your score**: Y / (Total - NA) x 100
5. **Identify top 3 gaps** and create remediation tasks
6. **Send results via HERMES relay** for bilateral comparison

### What You Need Before Starting

- Claude Code installed and configured (`claude --version`)
- Access to `~/.claude/` directory
- Basic familiarity with CLAUDE.md, skills, and settings
- 30-60 minutes for the full assessment

### Category Priority for New Users

Start with these (highest impact, lowest effort):

1. **C1 CLAUDE.md** — Foundation of everything
2. **C2 Memory** — Cross-session learning
3. **C10 Git** — Code safety
4. **C3 Skills** — Workflow automation
5. **C6 Settings** — Permissions and safety

Then graduate to:

6. **C5 Hooks** — Event-driven automation
7. **C4 Subagents** — Task delegation
8. **C7 MCP** — External integrations
9. **C8 Plan Mode** — Safe architecture work

---

## Bilateral Exchange Protocol

### Phase 2: JEI Self-Assessment (target 2026-03-22)

1. JEI receives this checklist via HERMES relay
2. JEI runs assessment independently against their setup
3. JEI sends results back via relay: score per category + top gaps
4. Both clans compare and identify shared improvement areas

### Phase 3: Dashboard & Remediation (target 2026-03-24)

1. Assessment scores exported as JSON for clan-dashboard
2. Dashboard widget shows: overall score, per-category breakdown, trend
3. Both clans create remediation tasks for top gaps
4. Re-assessment scheduled for +2 weeks to track improvement

### Relay Message Format

```json
{
  "ts": "2026-03-22",
  "src": "jei",
  "dst": "dani",
  "type": "data_cross",
  "msg": "QUEST-004 assessment: score=XX%, gaps=[...]",
  "ttl": 7,
  "ack": []
}
```

---

## References

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [Claude Code GitHub](https://github.com/anthropics/claude-code)
- ARC-5322 (HERMES Message Format)
- ARC-8446 (Encrypted Bus Protocol)
- QUEST-001, QUEST-002, QUEST-003 (bilateral quest precedents)
