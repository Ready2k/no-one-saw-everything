#!/usr/bin/env bash
# Stops the generative-agents simulation (reverie.py + run_stepper.py) and the
# Django environment server. These processes detach from the terminal that
# launched them, so closing the terminal window does NOT stop them — they
# keep running (and keep calling the LLM) until killed explicitly.
set -u
REPO="$(cd "$(dirname "$0")" && pwd)"

echo "Looking for generative-agents processes..."

PATTERNS=(
  "reverie.py"
  "run_stepper.py"
  "manage.py runserver"
)

FOUND_ANY=0
for pat in "${PATTERNS[@]}"; do
  PIDS=$(pgrep -f "$REPO.*$pat" || true)
  if [[ -n "$PIDS" ]]; then
    FOUND_ANY=1
    for pid in $PIDS; do
      CMD=$(ps -p "$pid" -o command= 2>/dev/null)
      echo "  Stopping PID $pid ($pat): $CMD"
      kill "$pid" 2>/dev/null
    done
  fi
done

if [[ "$FOUND_ANY" -eq 0 ]]; then
  echo "No matching processes found."
  exit 0
fi

# Give them a moment to shut down cleanly, then force-kill any stragglers.
sleep 2
for pat in "${PATTERNS[@]}"; do
  PIDS=$(pgrep -f "$REPO.*$pat" || true)
  for pid in $PIDS; do
    echo "  Force-killing PID $pid ($pat)"
    kill -9 "$pid" 2>/dev/null
  done
done

echo "Done. Verifying no requests are still in flight to the LLM endpoint..."
sleep 1
REMAINING=$(pgrep -f "$REPO.*(reverie.py|run_stepper.py|manage.py runserver)" || true)
if [[ -n "$REMAINING" ]]; then
  echo "WARNING: still running: $REMAINING"
  exit 1
else
  echo "All simulation/environment processes stopped."
fi
