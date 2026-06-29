#!/usr/bin/env bash
# Starts the generative-agents environment (Django frontend) server.
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$REPO/.venv/bin/python"
cd "$REPO/environment/frontend_server"
echo "Starting Django environment server at http://localhost:8000 ..."
exec "$PYTHON" manage.py runserver
