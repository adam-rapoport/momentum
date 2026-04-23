"""List Gemini/Gemma models visible to our Google AI Studio API key.

Read-only. Hits the public ListModels endpoint and prints the subset that
supports text generation (generateContent / streamGenerateContent), plus
their input/output token limits. Pricing is NOT returned by the API — see
https://ai.google.dev/gemini-api/docs/pricing for rates.

Usage:
  .venv/bin/python -m scripts.list_google_models
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.config import settings


def main() -> None:
    key = settings.google_ai_api_key
    if not key:
        print("GOOGLE_AI_API_KEY is not set in .env — add it and re-run.")
        sys.exit(1)

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    try:
        resp = httpx.get(url, params={"key": key}, timeout=15.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"API call failed: {e}")
        sys.exit(1)

    data = resp.json()
    models = data.get("models", [])
    gen_models: list[dict] = []
    for m in models:
        methods = set(m.get("supportedGenerationMethods") or [])
        # Keep only models that can do chat/text generation.
        if "generateContent" in methods or "streamGenerateContent" in methods:
            gen_models.append(m)

    # Sort by base family, newest first where possible.
    def sort_key(m: dict) -> tuple:
        name = m.get("name", "").lower()
        # Push "latest" variants up, then reverse alphabetical roughly puts
        # newer versions (3.x > 2.x) first.
        is_latest = "latest" in name
        return (not is_latest, name)

    gen_models.sort(key=sort_key, reverse=False)

    print(f"{len(gen_models)} text-generation models visible to this key:\n")
    print(f"{'NAME':<50} {'INPUT_TOK':>10} {'OUTPUT_TOK':>10}  DISPLAY / NOTES")
    print("-" * 120)
    for m in gen_models:
        # Trim the "models/" prefix the API returns.
        name = m.get("name", "").removeprefix("models/")
        display = m.get("displayName", "")
        in_limit = m.get("inputTokenLimit", "?")
        out_limit = m.get("outputTokenLimit", "?")
        desc = m.get("description", "").split("\n")[0][:60]
        label = f"{display[:40]}" + (f" — {desc}" if desc else "")
        print(f"{name:<50} {str(in_limit):>10} {str(out_limit):>10}  {label}")

    print()
    print("Pricing (not returned by API) — check the official table:")
    print("  https://ai.google.dev/gemini-api/docs/pricing")
    print()
    print(
        "Free-tier rate limits: see the 'Free' column at "
        "https://ai.google.dev/gemini-api/docs/rate-limits"
    )


if __name__ == "__main__":
    main()
