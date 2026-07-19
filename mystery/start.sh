#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"
mkdir -p "$PID_DIR"

BACKEND_LOG="$SCRIPT_DIR/backend.log"
FRONTEND_LOG="$SCRIPT_DIR/frontend.log"
BACKEND_PORT="${MYSTERY_API_PORT:-8010}"
FRONTEND_PORT="${MYSTERY_FRONTEND_PORT:-5179}"

# ── Backend ──────────────────────────────────────────────────────────────────
echo "▶  Starting backend..."

# Bootstrap venv if missing
if [ ! -f "$SCRIPT_DIR/backend/.venv/bin/uvicorn" ]; then
  echo "   No venv found — installing dependencies..."
  python3 -m venv "$SCRIPT_DIR/backend/.venv"
  "$SCRIPT_DIR/backend/.venv/bin/pip" install -q -r "$SCRIPT_DIR/backend/requirements.txt"
fi

"$SCRIPT_DIR/backend/.venv/bin/uvicorn" app.main:app \
  --port "$BACKEND_PORT" \
  --app-dir "$SCRIPT_DIR/backend" \
  >> "$BACKEND_LOG" 2>&1 &
echo $! > "$PID_DIR/backend.pid"
echo "   Backend  → http://localhost:$BACKEND_PORT  (pid $(cat "$PID_DIR/backend.pid"), log: backend.log)"

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "▶  Starting frontend..."

if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
  echo "   node_modules missing — running npm install..."
  npm --prefix "$SCRIPT_DIR/frontend" install --silent
fi

MYSTERY_API_PORT="$BACKEND_PORT" npm --prefix "$SCRIPT_DIR/frontend" run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" \
  >> "$FRONTEND_LOG" 2>&1 &
echo $! > "$PID_DIR/frontend.pid"
echo "   Frontend → http://localhost:$FRONTEND_PORT  (pid $(cat "$PID_DIR/frontend.pid"), log: frontend.log)"

echo ""
echo "✅  Game is running. Run ./stop.sh to shut it down."
