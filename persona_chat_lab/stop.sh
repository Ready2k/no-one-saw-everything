#!/usr/bin/env bash
set -euo pipefail

PORT="${PERSONA_CHAT_PORT:-8765}"
PIDS="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN || true)"

if [[ -z "$PIDS" ]]; then
  echo "Persona Chat Lab is not running on port $PORT."
  exit 0
fi

kill $PIDS
echo "Stopped Persona Chat Lab on port $PORT."
