#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"

stop_pid() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"

  if [ ! -f "$pid_file" ]; then
    echo "   $name: no pid file found (already stopped?)"
    return
  fi

  local pid
  pid=$(cat "$pid_file")

  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "   $name stopped (pid $pid)"
  else
    echo "   $name: process $pid not running"
  fi

  rm -f "$pid_file"
}

echo "■  Stopping mystery game..."
stop_pid backend
stop_pid frontend
echo ""
echo "✅  All processes stopped."
