---
topic: Agent SDK
updated: 2026-03-25
---

# Claude Agent SDK — Reference

## Overview
The Agent SDK gives programmatic access to the same tools, agent loop, and context management that power Claude Code. Available in Python and TypeScript.

## Installation
- Python: `pip install claude-agent-sdk`
- TypeScript: `npm install @anthropic-ai/claude-agent-sdk`

## Quick Example (Python)

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for message in query(
        prompt="Find and fix the bug in auth.py",
        options=ClaudeAgentOptions(allowed_tools=["Read", "Edit", "Bash"]),
    ):
        print(message)

asyncio.run(main())
```

## Built-in Tools
Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion, Agent (subagents), NotebookEdit

## Advanced Features
- **Hooks**: Lifecycle automation (PreToolUse, PostToolUse, Stop, SessionStart, SessionEnd)
- **Subagents**: Specialized parallel workers
- **MCP Integration**: Connect to 5000+ external systems
- **Sessions**: Resume, maintain context across exchanges
- **Skills & Memory**: Auto-loads .claude/skills/, CLAUDE.md
- **Structured Outputs**: JSON Schema validation

## Authentication
- Native API key (default)
- Amazon Bedrock (CLAUDE_CODE_USE_BEDROCK=1)
- Google Vertex AI (CLAUDE_CODE_USE_VERTEX=1)
- Microsoft Azure (CLAUDE_CODE_USE_FOUNDRY=1)

## Key Patterns

### Bare Mode (scripted)
```bash
claude --bare "Analyze this codebase and list all TODO comments"
```
No UI, no interactivity — direct output for pipelines.

### Subagent Delegation
```python
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Edit", "Bash", "Agent"],
    max_subagents=5,
)
```

### MCP in SDK
```python
options = ClaudeAgentOptions(
    mcp_servers={"github": {"command": "npx", "args": ["@anthropic/mcp-github"]}},
)
```

## Repos
- Python: github.com/anthropics/claude-agent-sdk-python
- TypeScript: github.com/anthropics/claude-agent-sdk-typescript
- Demos: github.com/anthropics/claude-agent-sdk-demos

## Clan Impact

The Agent SDK enables building production automation on top of Claude Code patterns:

| Use Case | Clan Application | Status |
|----------|-----------------|--------|
| CI/CD code review | PR review automatico Nymyka repos | Evaluado |
| Custom deployment bots | Render deploy verification | Candidato |
| Automated testing | QA-Engineer skill automation | Candidato |
| Batch processing | Heraldo bulk email scan | Candidato |
| Structured outputs | HERMES message validation | Candidato |

The SDK is the bridge between Daniel's interactive Claude Code workflow and production-grade automation.
