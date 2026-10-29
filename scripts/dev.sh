#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -d ".venv" ]; then
  echo "[The Last Clue] Creating Python virtual environment..."
  python3 -m venv --copies .venv
  .venv/bin/pip install -r python/requirements-dev.txt
fi

if [ ! -f "python/last_clue/static/index.html" ]; then
  "${ROOT_DIR}/scripts/build.sh"
fi

echo "[The Last Clue] Starting server on http://${LAST_CLUE_HOST:-0.0.0.0}:${LAST_CLUE_PORT:-8765} ..."
exec .venv/bin/python python/main.py
