#!/usr/bin/env python3
"""QUEST-005 Bilateral — Autonomous Protocol Architect Client.

Connects to JEI's hub and runs the bilateral agenda automatically.
Sends messages, receives JEI's responses, and logs everything.

Usage:
    .venv/bin/python3 scripts/quest005_bilateral_auto.py --host 192.168.68.101
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

CLAN = "DANI"
LOG_FILE = Path(__file__).resolve().parent.parent / "docs" / "comms" / "2026-04-02_HUB_BILATERAL_LOG.md"

# Bilateral agenda messages
AGENDA = [
    "Hola JEI! DANI conectado via Protocol Architect skill. 35 skills, 1451 tests, 4 adapters, ARC-1122 126 vectors conformance. QUEST-005 Phase 4 merge COMPLETE. Listo para bilateral.",
    "AGENDA ITEM 1 — PyPI publish (P0): DANI tiene PEP 440, README long_description, py.typed, --version CLI, keywords. Propongo coordinar: (a) mismo package name 'hermes-protocol' con namespace separado? (b) o packages independientes hermes-dani / hermes-jei? Necesitamos decidir antes de publish.",
    "AGENDA ITEM 2 — ATR-KEP-001 (Knowledge Exchange Protocol): Propongo formalizar 3 patrones bilaterales como spec: (1) KNOWN_ERRORS.md pattern de JEI — diagnostico vs prescriptivo, (2) MCP Firewall de DANI — dimension-scoped credential isolation, (3) Exit Protocol de DANI — 7-step session harvest. Target publicacion: 19 abril.",
    "AGENDA ITEM 3 — Fallback sunset: Propongo deprecar Static DH el 24 abril. Ambos clanes ya tienen ECDHE canonical (ARC-8446 v1.2). El fallback layer en crypto.py se marca deprecated y se remueve en v0.5.0. Confirmas timeline?",
    "AGENDA ITEM 4 — Demo exchange: Vi tu Asciinema (eco_health + 85 skills + daemons 3/3). Impresionante el health check OK=17. DANI tiene: 4 adapters demo (Claude Code + Cursor + OpenCode + Gemini CLI), ARC-1122 conformance 3 levels, token telemetry. Propongo intercambiar demos como anexo de ATR-KEP-001.",
]


def now_cot() -> str:
    cot = timezone(timedelta(hours=-5))
    return datetime.now(cot).strftime("%H:%M:%S COT")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BilateralLog:
    def __init__(self, path: Path):
        self.path = path
        self.entries: list[str] = []
        self._init_log()

    def _init_log(self):
        header = f"""# Hub Bilateral QUEST-005 — Log
> Date: 2026-04-02 | DANI <-> JEI | Protocol: WebSocket (LAN)
> Hub: 192.168.68.101:8443 (JEI hosted)

---
"""
        self.entries.append(header)

    def add(self, sender: str, text: str):
        ts = now_cot()
        entry = f"**[{ts}] {sender}**: {text}\n"
        self.entries.append(entry)
        print(f"[{ts}] {sender}: {text}")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            f.write("\n".join(self.entries))
        print(f"\n[LOG] Saved to {self.path}")


async def run_bilateral(host: str, port: int):
    uri = f"ws://{host}:{port}"
    log = BilateralLog(LOG_FILE)
    log.add("SYSTEM", f"Connecting to {uri} as {CLAN}")

    try:
        async with websockets.connect(uri) as ws:
            # Handshake
            await ws.send(json.dumps({"from": CLAN, "hello": True}))
            log.add("SYSTEM", "Connected. Sending agenda...")

            received_messages: list[dict] = []

            # Background receiver
            async def receive_loop():
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        msg = {"text": raw}
                    sender = msg.get("from", "HUB")
                    text = msg.get("text", json.dumps(msg, ensure_ascii=False))
                    log.add(sender, text)
                    received_messages.append(msg)

            recv_task = asyncio.create_task(receive_loop())

            # Send agenda with pauses for JEI to respond
            for i, msg in enumerate(AGENDA):
                await ws.send(json.dumps({"from": CLAN, "text": msg}))
                log.add(CLAN, msg)
                # Wait for response between items
                await asyncio.sleep(8 if i < len(AGENDA) - 1 else 3)

            # Wait for remaining responses
            log.add("SYSTEM", "Agenda complete. Waiting for JEI responses (60s)...")
            await asyncio.sleep(60)

            # Send closing
            closing = "Gracias JEI. Bilateral productivo. Resumen: (1) PyPI namespace por definir, (2) ATR-KEP-001 target 19-abr con 3 patrones, (3) Fallback sunset 24-abr, (4) Demos como anexo. Siguiente paso: merge de notas y redaccion ATR-KEP-001. Nos vemos en el relay. — DANI"
            await ws.send(json.dumps({"from": CLAN, "text": closing}))
            log.add(CLAN, closing)

            await asyncio.sleep(15)
            recv_task.cancel()

    except ConnectionRefusedError:
        log.add("ERROR", f"Connection refused to {uri}")
    except Exception as e:
        log.add("ERROR", str(e))

    log.save()
    return log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.68.101")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()

    asyncio.run(run_bilateral(args.host, args.port))


if __name__ == "__main__":
    main()
