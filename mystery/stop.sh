#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"
BACKEND_PORT="${MYSTERY_API_PORT:-8010}"
FRONTEND_PORT="${MYSTERY_FRONTEND_PORT:-5179}"

process_belongs_to_project() {
  local pid="$1"
  local command
  local process_cwd
  command=$(ps -p "$pid" -o command= 2>/dev/null || true)
  process_cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1)
  [[ "$command" == *"$SCRIPT_DIR"* || "$process_cwd" == "$SCRIPT_DIR"* ]]
}

stop_tree() {
  local pid="$1"
  local child

  # Stop children first. npm launches Vite as a child process, and signalling
  # npm alone can leave the actual server orphaned and still listening.
  while IFS= read -r child; do
    [ -n "$child" ] && stop_tree "$child"
  done < <(pgrep -P "$pid" 2>/dev/null || true)

  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
}

wait_for_exit() {
  local pid="$1"
  local attempt
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$pid" 2>/dev/null || return
    sleep 0.1
  done
  kill -KILL "$pid" 2>/dev/null || true
}

stop_pid_file() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"

  if [ ! -f "$pid_file" ]; then
    return
  fi

  local pid
  pid=$(cat "$pid_file")

  if kill -0 "$pid" 2>/dev/null; then
    if process_belongs_to_project "$pid"; then
      stop_tree "$pid"
      wait_for_exit "$pid"
      echo "   $name stopped (pid $pid)"
    else
      echo "   $name: ignored stale pid $pid (belongs to another process)"
    fi
  else
    echo "   $name: process $pid not running"
  fi

  rm -f "$pid_file"
}

stop_listener() {
  local name="$1"
  local port="$2"
  local pid
  local found=0

  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    found=1
    if process_belongs_to_project "$pid"; then
      stop_tree "$pid"
      wait_for_exit "$pid"
      echo "   $name listener stopped (pid $pid, port $port)"
    else
      echo "   $name: port $port is used by another project (pid $pid); left running"
    fi
  done < <(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u)

  [ "$found" -eq 1 ] || echo "   $name: already stopped"
}

echo "■  Stopping mystery game..."
stop_pid_file frontend
stop_pid_file backend

# PID files can be absent after an interrupted stop or overwritten by another
# start attempt. Recover by checking the configured ports, but only terminate
# commands whose full path proves they belong to this workspace.
stop_listener frontend "$FRONTEND_PORT"
stop_listener backend "$BACKEND_PORT"
echo ""
echo "✅  All processes stopped."
