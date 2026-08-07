#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PERSONA_CHAT_PORT:-8765}"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Persona Chat Lab is already running at http://localhost:$PORT/"
  exit 0
fi

cd "$SCRIPT_DIR"
exec python3 -u server.py
