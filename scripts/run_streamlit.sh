#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH=$(pwd)
PORT=${1:-8501}
uv run streamlit run streamlit_app/app.py --server.port "$PORT" --server.address 127.0.0.1

