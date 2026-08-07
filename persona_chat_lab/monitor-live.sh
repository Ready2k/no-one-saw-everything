#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while true; do
  clear
  "$SCRIPT_DIR/monitor.sh"
  echo
  echo "Updates every 2 seconds. Press Ctrl-C to stop monitoring."
  sleep 2
done
