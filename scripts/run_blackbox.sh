#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/run_blackbox.sh [on|off] [port]
# Defaults: guardrail=off, port=8000

GUARD=${1:-off}
PORT=${2:-8000}

if [[ "$GUARD" == "on" ]]; then
  export RAG_GUARDRAIL=1
else
  export RAG_GUARDRAIL=0
fi

echo "[blackbox] guardrail=$RAG_GUARDRAIL port=$PORT"

if [[ "$PORT" == "8000" ]]; then
  uv run python blackbox/simple-rag-server.py
else
  uv run uvicorn blackbox.simple-rag-server:app --port "$PORT"
fi

