# Demo: Local AI Swarm

Two AI agents collaborate on the same project through HERMES -- no cloud, no API keys, no servers.

## What you'll see

1. **Claude Code** writes a backend API
2. Claude Code sends a HERMES message describing the API to Cursor
3. **Cursor** reads the message and builds the matching frontend
4. All coordination happens through a local file (`bus.jsonl`)

## Prerequisites

- Python 3.11+
- [Claude Code](https://claude.ai/code) installed
- [Cursor](https://cursor.com) installed
- Both tools open in the same project directory

## Setup (< 3 minutes)

### 1. Install HERMES

```bash
pip install hermes-protocol
hermes init --clan-id my-team --display-name "My Team"
```

### 2. Connect both agents

```bash
hermes adapt claude-code    # installs MCP server + hooks
hermes adapt cursor         # generates .cursorrules + bus symlink
```

### 3. (Optional) Enable Cursor MCP for two-way messaging

Create `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "hermes-bus": {
      "command": "hermes",
      "args": ["mcp", "serve"]
    }
  }
}
```

Without this, Cursor can read messages but not send them back.

## Run the demo

### Terminal 1: Claude Code

Open Claude Code in your project directory and say:

```
Create a FastAPI backend for a todo app with GET /todos and POST /todos endpoints.
When done, send a HERMES message to "cursor" with the API spec.
```

Claude Code will:
1. Write the FastAPI code
2. Call `hermes_bus_write(src="claude-code", dst="cursor", type="dispatch", msg="API ready: GET /todos returns [{id,title,done}], POST /todos accepts {title}")`

### Terminal 2: Cursor

Open Cursor in the same project directory. The HERMES message appears in Cursor's context (via `.cursorrules` or MCP). Say:

```
Read the HERMES message from claude-code and build a React frontend for the todo API.
```

Cursor builds the frontend based on the API spec it received through HERMES.

## What just happened?

```
Claude Code                          Cursor
    |                                   |
    | 1. Writes backend code            |
    |                                   |
    | 2. hermes_bus_write()             |
    |     src: claude-code              |
    |     dst: cursor                   |
    |     msg: "API ready: ..."         |
    |          |                        |
    |          v                        |
    |   ~/.hermes/bus.jsonl             |
    |          |                        |
    |          +------------------------> 3. Reads message
    |                                   |
    |                                   | 4. Builds frontend
```

No server. No cloud. No API keys. Just a JSON file on your disk that both agents can read.

## Verify

```bash
# See all messages
cat ~/.hermes/bus.jsonl | jq .

# See what cursor received
cat ~/.hermes/bus.jsonl | grep '"dst":"cursor"'

# Check HERMES status
hermes status
```

## Next steps

- **Add more agents**: `hermes adapt gemini` or `hermes adapt opencode`
- **Encrypt messages**: `hermes peer invite` to set up E2E encryption with a collaborator
- **Go real-time**: `hermes hub install` for WebSocket-based live messaging
- **Monitor costs**: `hermes llm usage` to track token spend across AI backends
