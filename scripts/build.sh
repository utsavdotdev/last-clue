#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[The Last Clue] Installing frontend dependencies and compiling bundle..."
cd "${ROOT_DIR}/frontend"
npm install
npm run build

echo "[The Last Clue] Production bundle compiled into python/last_clue/static/"
