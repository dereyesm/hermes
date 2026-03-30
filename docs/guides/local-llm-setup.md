# Local LLM Setup Guide

> Run AI models locally for privacy, cost savings, and offline capability — integrated with HERMES and OpenCode.

This guide covers deploying a local LLM on **macOS**, **Linux**, and **Windows 11+**, connecting it to [OpenCode](https://opencode.ai) as a coding assistant, and integrating it with HERMES via the adapter pattern.

## Table of Contents

- [Overview](#overview)
- [Quickstart (5 minutes)](#quickstart-5-minutes)
- [Platform Guides](#platform-guides)
  - [macOS (Apple Silicon)](#macos-apple-silicon)
  - [Linux](#linux)
  - [Windows 11+](#windows-11)
- [OpenCode Integration](#opencode-integration)
- [HERMES Adapter Integration](#hermes-adapter-integration)
- [Recommended Models](#recommended-models)
- [Troubleshooting](#troubleshooting)

---

## Overview

### Architecture

```
You (terminal)
  |
  ├── OpenCode (TUI) ──→ Local LLM Server ──→ Model (Qwen, Llama, Mistral, etc.)
  |                        :8008 or :11434
  └── HERMES ──→ AdapterManager ──→ OpenAICompatibleAdapter ──→ Local LLM Server
                     |
                     ├──→ ClaudeAdapter (cloud, premium)
                     ├──→ GeminiAdapter (cloud, free tier)
                     └──→ OllamaAdapter / MLXAdapter (local, $0)
```

### What You Get

| Feature | Local | Cloud |
|---------|-------|-------|
| Cost | $0 | Per-token |
| Privacy | 100% local | Data sent to provider |
| Speed | Hardware-dependent | Fast (API) |
| Offline | Yes | No |
| Quality (complex tasks) | Good for coding | Best (Claude, GPT) |

### Vendor Neutrality

HERMES is **vendor-neutral**. This guide uses [Qwen 2.5 Coder](https://qwenlm.github.io/blog/qwen2.5-coder-family/) as the quickstart example because it's open-source, performant for coding, and available in sizes from 0.5B to 32B. You can substitute **any compatible model**: Llama 3, Mistral, DeepSeek Coder, CodeGemma, StarCoder, etc.

---

## Quickstart (5 minutes)

Pick your platform and follow the minimal path:

### macOS (Apple Silicon M1-M5)

```bash
# 1. Install MLX
uv tool install mlx-lm
# Or: pip install mlx-lm

# 2. Run a model
mlx_lm.chat --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit
```

### Linux / Windows (WSL2)

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull and run a model
ollama run qwen2.5-coder:7b
```

### Windows 11+ (Native)

```powershell
# 1. Download installer from https://ollama.com/download/windows
# 2. Run in terminal:
ollama run qwen2.5-coder:7b
```

**That's it.** You now have a local LLM. Read on for OpenCode and HERMES integration.

---

## Platform Guides

### macOS (Apple Silicon)

#### Why MLX instead of Ollama?

[MLX](https://github.com/ml-explore/mlx) is Apple's ML framework, optimized for Apple Silicon. It provides native Metal support across all M-series chips (M1 through M5+) without compatibility issues.

> **Note**: As of March 2026, Ollama has a Metal shader compatibility issue with M5 chips (`bfloat16` vs `half` type mismatch in MetalPerformancePrimitives). If you're on M1-M4, Ollama works fine. On M5+, use MLX.

#### Install MLX

```bash
# Recommended (isolated install)
uv tool install mlx-lm

# Alternative (pip)
pip install mlx-lm
```

#### Download and Test a Model

```bash
# Interactive chat
mlx_lm.chat --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit

# One-shot generation
mlx_lm.generate \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --prompt "Write a Python function to merge two sorted lists" \
  --max-tokens 300
```

#### Start the API Server

MLX provides an OpenAI-compatible API server:

```bash
mlx_lm.server \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --port 8008
```

Test it:

```bash
curl http://localhost:8008/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }'
```

#### Auto-Start on Login (launchd)

Create `~/Library/LaunchAgents/com.hermes.mlx-server.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hermes.mlx-server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USER/.local/bin/mlx_lm.server</string>
        <string>--model</string>
        <string>mlx-community/Qwen2.5-Coder-7B-Instruct-4bit</string>
        <string>--port</string>
        <string>8008</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/mlx-server.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/mlx-server.log</string>
</dict>
</plist>
```

```bash
# Replace YOUR_USER with your username, then:
launchctl load ~/Library/LaunchAgents/com.hermes.mlx-server.plist

# Verify
curl -s http://localhost:8008/v1/models | python3 -m json.tool
```

#### Performance Reference (Apple Silicon)

| Chip | Model | Tokens/sec | Peak RAM |
|------|-------|-----------|----------|
| M1 | Qwen 2.5 Coder 7B-4bit | ~15 | 4.4 GB |
| M2 | Qwen 2.5 Coder 7B-4bit | ~20 | 4.4 GB |
| M3 | Qwen 2.5 Coder 7B-4bit | ~25 | 4.4 GB |
| M5 | Qwen 2.5 Coder 7B-4bit | ~28 | 4.4 GB |

---

### Linux

#### Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### GPU Setup

**NVIDIA** (recommended):
```bash
# Verify driver (531+ required, 535+ recommended)
nvidia-smi

# If missing:
sudo ubuntu-drivers autoinstall
# Reboot, then verify: nvidia-smi
```

No separate CUDA toolkit install needed — Ollama bundles its own runtime.

**AMD** (ROCm):
```bash
# RX 7700+ / Ryzen AI 300+:
# Install latest Adrenalin driver from amd.com (includes ROCm)

# Older GPUs — install ROCm manually:
sudo apt-get install rocm-hip-sdk

# If your GPU GFX version isn't supported:
export HSA_OVERRIDE_GFX_VERSION=gfx906
```

**CPU-only**: Works out of the box, but 5-10x slower than GPU.

#### Run a Model

```bash
ollama pull qwen2.5-coder:7b
ollama run qwen2.5-coder:7b
```

#### Start the API Server

Ollama exposes an OpenAI-compatible API on port 11434 by default:

```bash
# Start as service
ollama serve

# Test
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:7b",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }'
```

#### Auto-Start (systemd)

```bash
# Ollama install script usually creates this automatically.
# Verify:
systemctl status ollama

# If not running:
sudo systemctl enable ollama
sudo systemctl start ollama
```

#### Docker Alternative

```bash
docker run -d \
  --name ollama \
  --gpus all \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama

docker exec -it ollama ollama pull qwen2.5-coder:7b
```

---

### Windows 11+

Two paths: **Native** (simpler) or **WSL2** (better dev experience).

#### Option A: Native Windows

1. Download installer from [ollama.com/download/windows](https://ollama.com/download/windows)
2. Run `OllamaSetup.exe` (no admin rights needed)
3. Open PowerShell:

```powershell
ollama pull qwen2.5-coder:7b
ollama run qwen2.5-coder:7b
```

GPU support: NVIDIA auto-detected with driver 531+ (update via GeForce Experience). AMD not yet supported natively.

#### Option B: WSL2 (Recommended for Developers)

```powershell
# 1. Install WSL2
wsl --install Ubuntu
wsl --update

# 2. Enter WSL
wsl
```

Inside WSL:

```bash
# 3. Install Ollama
sudo apt update && sudo apt install -y zstd
curl -fsSL https://ollama.com/install.sh | sh

# 4. Start and test
ollama serve &
ollama pull qwen2.5-coder:7b
ollama run qwen2.5-coder:7b
```

**GPU passthrough**: Install NVIDIA driver on **Windows only** (not inside WSL). WSL2 detects it automatically.

**Memory config** — edit `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
memory=12GB
```

Then restart WSL: `wsl --shutdown`

---

## OpenCode Integration

[OpenCode](https://opencode.ai) is an open-source terminal UI for AI-assisted coding. It supports local models via any OpenAI-compatible API.

### Install OpenCode

```bash
# All platforms
curl -fsSL https://opencode.ai/install | bash
```

### Configure for Local LLM

Create `opencode.json` in your project root (or `~/.opencode/config.json` for global):

**For MLX (macOS):**

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "mlx-local": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "MLX Local",
      "options": {
        "baseURL": "http://localhost:8008/v1"
      },
      "models": {
        "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit": {
          "name": "Qwen 2.5 Coder 7B (local)"
        }
      }
    }
  }
}
```

**For Ollama (Linux/Windows):**

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": {
        "baseURL": "http://localhost:11434/v1"
      },
      "models": {
        "qwen2.5-coder:7b": {
          "name": "Qwen 2.5 Coder 7B (local)"
        }
      }
    }
  }
}
```

### Run OpenCode with Local Model

```bash
# MLX
opencode -m mlx-local/mlx-community/Qwen2.5-Coder-7B-Instruct-4bit

# Ollama
opencode -m ollama/qwen2.5-coder:7b
```

---

## HERMES Adapter Integration

HERMES uses an adapter pattern to support multiple LLM backends. Adding local model support means implementing or configuring an `OpenAICompatibleAdapter`.

### Architecture

```python
from hermes.llm import LLMAdapter, LLMResponse, AdapterManager

class OpenAICompatibleAdapter(LLMAdapter):
    """Adapter for any OpenAI-compatible API (Ollama, MLX, vLLM, etc.)"""

    def __init__(self, base_url: str, model: str, name_prefix: str = "local"):
        self.base_url = base_url
        self.model = model
        self._name_prefix = name_prefix

    def complete(self, system_prompt: str, user_message: str,
                 max_tokens: int = 4096) -> LLMResponse:
        import requests
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": max_tokens,
            },
        )
        data = response.json()
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            backend=self._name_prefix,
            model=self.model,
        )

    def name(self) -> str:
        return f"{self._name_prefix}/{self.model}"

    def health_check(self) -> bool:
        import requests
        try:
            r = requests.get(f"{self.base_url}/v1/models", timeout=3)
            return r.status_code == 200
        except Exception:
            return False
```

### Configuration

In your HERMES `config.toml`:

```toml
[hermes]
default_backend = "claude"
fallback_order = ["claude", "gemini", "local"]

# Cloud backends
[[llm.backends]]
backend = "claude"
model = "claude-sonnet-4-6"
api_key_env = "ANTHROPIC_API_KEY"
enabled = true

[[llm.backends]]
backend = "gemini"
model = "gemini-2.5-flash"
api_key_env = "GEMINI_API_KEY"
enabled = true

# Local backend (MLX on macOS, Ollama on Linux/Windows)
[[llm.backends]]
backend = "openai-compatible"
model = "qwen2.5-coder:7b"               # or mlx-community/Qwen2.5-Coder-7B-Instruct-4bit
base_url = "http://localhost:8008/v1"     # MLX: 8008, Ollama: 11434
enabled = true
```

### Tiered Routing

Use `model` hints in skill frontmatter to route to the right backend:

```yaml
---
name: palas
description: Strategic observer
model: opus          # Routes to Claude (premium)
---
```

```yaml
---
name: health-check
description: Quick system check
model: local         # Routes to local LLM ($0)
---
```

The `AdapterManager` resolves hints to backends via the fallback order.

---

## Recommended Models

| Model | Size | Best For | Ollama | MLX (4-bit) |
|-------|------|----------|--------|-------------|
| **Qwen 2.5 Coder 7B** | 4.7 GB | Code generation, refactoring | `qwen2.5-coder:7b` | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` |
| **Qwen 2.5 Coder 14B** | 9 GB | Complex coding (needs 32GB RAM) | `qwen2.5-coder:14b` | `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` |
| **Llama 3.2 3B** | 2 GB | Fast, lightweight tasks | `llama3.2:3b` | `mlx-community/Llama-3.2-3B-Instruct-4bit` |
| **Mistral 7B** | 4.1 GB | General purpose | `mistral:7b` | `mlx-community/Mistral-7B-Instruct-v0.3-4bit` |
| **DeepSeek Coder V2** | 8.9 GB | Code + reasoning | `deepseek-coder-v2:16b` | `mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit` |
| **CodeGemma 7B** | 5 GB | Code completion | `codegemma:7b` | `mlx-community/CodeGemma-7B-IT-4bit` |

Choose based on your RAM:
- **8 GB**: Llama 3.2 3B or Qwen 2.5 Coder 7B (tight)
- **16 GB**: Qwen 2.5 Coder 7B (comfortable) or 14B (tight)
- **32 GB+**: Qwen 2.5 Coder 14B or 32B

---

## Troubleshooting

### macOS: Ollama fails on M5

**Symptom**: `static_assert failed: Input types must match cooperative tensor types`

**Cause**: Ollama's Metal shaders use `half` (float16) but M5's MetalPerformancePrimitives expect `bfloat16`.

**Fix**: Use MLX instead of Ollama on M5+ chips. See [macOS guide](#macos-apple-silicon).

### Linux: GPU not detected

```bash
# Check NVIDIA driver
nvidia-smi
# If missing: sudo ubuntu-drivers autoinstall && reboot

# Check AMD
rocm-smi
# If missing: install ROCm or latest Adrenalin driver
```

### Windows: Slow inference

1. Check GPU usage in Task Manager (Performance > GPU)
2. Update NVIDIA driver to 535+
3. If using WSL2, increase memory in `.wslconfig`

### OpenCode: Model not found

Ensure the local server is running before launching OpenCode:
- MLX: `curl http://localhost:8008/v1/models`
- Ollama: `curl http://localhost:11434/v1/models`

### General: Out of memory

- Use a smaller model (7B instead of 14B)
- Use 4-bit quantization (default in MLX, Q4_K_M in Ollama)
- Close other memory-heavy applications

---

## References

- [MLX Documentation](https://ml-explore.github.io/mlx/)
- [Ollama Documentation](https://docs.ollama.com)
- [OpenCode Documentation](https://opencode.ai/docs)
- [Qwen 2.5 Coder Family](https://qwenlm.github.io/blog/qwen2.5-coder-family/)
- [HERMES Multi-LLM Architecture](../architecture/ARC-MULTI-LLM-DESIGN.md)

---

*This guide is part of the [HERMES](https://github.com/hermes-protocol) project. HERMES is vendor-neutral and does not endorse any specific model or provider. Models listed are examples chosen for accessibility and performance.*
