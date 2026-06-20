#!/usr/bin/env bash
cd "$(dirname "$0")"
set -a; . ./.env; set +a
export LLM_PROVIDER=openrouter
exec python -m uvicorn backend.main:app --port 8000
