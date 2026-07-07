#!/usr/bin/env bash
# Boot an ISOLATED Momentum backend for skill eval runs.
#
# Why every export below exists (don't trim them):
#   - Real env vars beat backend/.env (pydantic-settings precedence), and a
#     dev .env typically pins DATABASE_URL to a real Postgres and GROQ_MODEL
#     to a non-shipped model. DATA_DIR alone does NOT override an explicit
#     DATABASE_URL, so both must be set here.
#   - GROQ_MODEL / GROQ_HEAVY_MODEL are pinned to the SHIPPED defaults so
#     evals measure what a new user actually gets.
#   - MOMENTUM_AUTH_TOKEN is unset so the runner needs no auth header.
#   - cwd stays backend/ so .env still supplies API keys (GOOGLE_AI_API_KEY).
#
# Usage: scripts/eval/serve_isolated.sh <data-dir> [port]
set -euo pipefail

DATA="${1:?usage: serve_isolated.sh <data-dir> [port]}"
PORT="${2:-8000}"
mkdir -p "$DATA"
DATA="$(cd "$DATA" && pwd)"   # absolutize before exporting

cd "$(dirname "$0")/../.."    # backend/

export DATA_DIR="$DATA"
export DATABASE_URL="sqlite+aiosqlite:///$DATA/momentum.db"
export MEMORY_ROOT="$DATA/memory"
export GROQ_MODEL="gemini-3.1-flash-lite"
export GROQ_HEAVY_MODEL="gemini-3.5-flash"
unset MOMENTUM_AUTH_TOKEN

echo "[serve_isolated] data dir: $DATA"
echo "[serve_isolated] pass --data-dir \"$DATA\" to run_live_skills"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
