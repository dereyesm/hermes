#!/usr/bin/env python3
"""Spike: Execute a real skill (Palas) via Gemini API.

This proves that:
1. SKILL.md can be loaded and converted to a universal system prompt
2. That prompt works with Gemini's API
3. The output is usable (follows skill instructions)

Usage:
    source ~/.secrets/nymyka.env
    uv run python test_spike.py
"""

import os
import sys
import time
from pathlib import Path

from skill_loader import SkillLoader
from adapters import GeminiAdapter, LLMResponse

# --- Config ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
PALAS_SKILL_PATH = Path.home() / ".claude/skills/palas/SKILL.md"


def main():
    if not GOOGLE_API_KEY:
        print("ERROR: GOOGLE_API_KEY not set. Run: source ~/.secrets/nymyka.env")
        sys.exit(1)

    if not PALAS_SKILL_PATH.exists():
        print(f"ERROR: Skill not found at {PALAS_SKILL_PATH}")
        sys.exit(1)

    # --- Step 1: Load Skill ---
    print("=" * 60)
    print("SPIKE: HERMES Multi-LLM Adapter — Palas via Gemini")
    print("=" * 60)

    loader = SkillLoader()
    skill = loader.load(PALAS_SKILL_PATH)

    print(f"\nSkill loaded: {skill.name}")
    print(f"  Description: {skill.description[:80]}...")
    print(f"  Model hint: {skill.model_hint}")
    print(f"  Prompt length: {len(skill.system_prompt)} chars")

    # --- Step 2: Convert to universal system prompt ---
    system_prompt = loader.to_system_prompt(skill, context={
        "fecha": "2026-03-28 (sabado)",
        "dimension_activa": "global (desde ~/Dev/)",
        "usuario": "Daniel Reyes (MomoshoD)",
        "nota": "Este es un spike de prueba del adapter multi-LLM. Palas opera via Gemini, no Claude.",
    })

    print(f"\nSystem prompt generated: {len(system_prompt)} chars")

    # --- Step 3: Initialize Gemini adapter ---
    print("\nInitializing Gemini adapter...")
    adapter = GeminiAdapter(api_key=GOOGLE_API_KEY, model="gemini-2.5-flash")
    print(f"  Backend: {adapter.name()}")

    # --- Step 4: Health check ---
    print("\nHealth check...")
    healthy = adapter.health_check()
    print(f"  Status: {'OK' if healthy else 'FAILED'}")
    if not healthy:
        print("Gemini not responding. Aborting.")
        sys.exit(1)

    # --- Step 5: Execute real query ---
    user_query = """Palas, necesito un health check rapido.

Contexto actual (resumido):
- Nymyka: Sprint 3 cierra hoy (28 Mar). Multi-agent router estable. PRs merged. Pending: costos, pricing tiers.
- MomoshoD: Dashboard v0.4.0 live. Nakama #1 publicado. Pending: difusion, Gear 5.
- MomoFinance: Plutus Score 29/100 (CRITICO). Visa rotativo pendiente de kill con salario Mar 31.
- Zima26: Sesion #82 = 24 Mar (pasada). Consejo voto 4-1 no renovar admin.
- HERMES: v0.4.2-alpha. QUEST-005 deadline Mar 29.

Dame el health check en tu formato standard."""

    print(f"\nSending query ({len(user_query)} chars)...")
    print("-" * 60)

    t0 = time.time()
    response: LLMResponse = adapter.complete(
        system_prompt=system_prompt,
        user_message=user_query,
        max_tokens=2048,
    )
    elapsed = time.time() - t0

    print(f"\nResponse from {response.backend}/{response.model}:")
    print(f"  Time: {elapsed:.1f}s")
    if response.usage:
        print(f"  Tokens in: {response.usage.get('input_tokens', '?')}")
        print(f"  Tokens out: {response.usage.get('output_tokens', '?')}")
    print("-" * 60)
    print(response.text)
    print("-" * 60)

    # --- Step 6: Quality assessment ---
    print("\n" + "=" * 60)
    print("QUALITY ASSESSMENT (manual)")
    print("=" * 60)
    checks = [
        ("Responded in Spanish", None),
        ("Used health check table format", None),
        ("Covered all 4+ dimensions", None),
        ("Identified risks", None),
        ("Gave actionable recommendations", None),
        ("Respected 'Palas observa, no ejecuta'", None),
        ("Mentioned cross-dimension risks", None),
    ]
    for check, _ in checks:
        print(f"  [ ] {check}")

    print(f"\nSPIKE COMPLETE. Gemini responded in {elapsed:.1f}s.")
    print("Review output above and score quality vs Claude equivalent.")


if __name__ == "__main__":
    main()
