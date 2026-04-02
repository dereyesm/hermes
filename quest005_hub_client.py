#!/usr/bin/env python3
from __future__ import annotations
"""
quest005_hub_client.py — Cliente REPL para el hub bilateral QUEST-005.

Conecta al hub como JEI, permite enviar mensajes y recibe del otro clan.

Uso:
  python3 scripts/quest005_hub_client.py             # conecta como JEI a :8443
  python3 scripts/quest005_hub_client.py --clan DANI # simular DANI (testing local)
  python3 scripts/quest005_hub_client.py --host x.x.x.x --port 8443

Comandos en el REPL:
  /status   — muestra estado de la conexión
  /quit     — cierra
  cualquier texto → enviado como mensaje al otro clan
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone, timedelta

try:
    import websockets
except ImportError:
    print("ERROR: pip3 install websockets")
    sys.exit(1)


def now_cot() -> str:
    cot = timezone(timedelta(hours=-5))
    return datetime.now(cot).strftime("%H:%M:%S COT")


async def run_client(clan: str, host: str, port: int) -> None:
    uri = f"ws://{host}:{port}"
    print(f"[{now_cot()}] Conectando a {uri} como {clan}...")

    try:
        async with websockets.connect(uri) as ws:
            # Handshake
            await ws.send(json.dumps({"from": clan, "hello": True}))
            print(f"[{now_cot()}] Conectado. Esperando al otro clan...")
            print("  Escribe un mensaje y Enter para enviar. /quit para salir.\n")

            # Tarea para recibir mensajes en background
            async def receive_loop():
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        msg = {"text": raw}
                    sender = msg.get("from", "?")
                    text = msg.get("text", json.dumps(msg, ensure_ascii=False))
                    print(f"\n[{now_cot()}] {sender}: {text}")
                    print("> ", end="", flush=True)

            recv_task = asyncio.create_task(receive_loop())

            # Loop de envío
            loop = asyncio.get_event_loop()
            while True:
                print("> ", end="", flush=True)
                line = await loop.run_in_executor(None, sys.stdin.readline)
                line = line.strip()
                if not line:
                    continue
                if line == "/quit":
                    break
                if line == "/status":
                    print(f"  Conectado como {clan} a {uri}")
                    continue
                await ws.send(json.dumps({
                    "from": clan,
                    "text": line,
                }))

            recv_task.cancel()

    except ConnectionRefusedError:
        print(f"ERROR: No se pudo conectar a {uri} — ¿está corriendo quest005_hub.py?")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCerrando cliente.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QUEST-005 Hub Client")
    parser.add_argument("--clan", default="JEI", help="Identificador de clan (default: JEI)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()

    asyncio.run(run_client(args.clan, args.host, args.port))
