#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/run_chainlit.sh [port]
# Default: port=8100

PORT=${1:-8100}
export PYTHONPATH=$(pwd)

echo "[chainlit] port=$PORT"
uv run chainlit run -w chainlit_app/app.py --host 127.0.0.1 --port "$PORT"
