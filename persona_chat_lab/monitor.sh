#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Persona Chat Lab status"
echo

if lsof -nP -iTCP:8765 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Web lab: running  http://localhost:8765/"
else
  echo "Web lab: stopped"
fi

RENDER_PIDS="$(pgrep -f 'LivePortrait/inference.py' || true)"
if [[ -n "$RENDER_PIDS" ]]; then
  echo "Face render: running (PID(s): ${RENDER_PIDS//$'\n'/, })"
  ps -o pid=,etime=,command= -p ${RENDER_PIDS//$'\n'/,} | sed 's/^/  /'
else
  echo "Face render: idle"
fi

echo
echo "Rendered candidates:"
shopt -s nullglob
for clip in /tmp/owen-*/*/owen_source--owen_*.mp4 /tmp/owen-*/owen_source--owen_*.mp4; do
  [[ -f "$clip" ]] && stat -f '  %N  (%z bytes)' "$clip"
done

echo
echo "For live updates on macOS:  ./monitor-live.sh"
