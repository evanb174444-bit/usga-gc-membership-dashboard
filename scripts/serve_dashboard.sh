#!/bin/zsh

set -e

SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h}"
PORT="${PORT:-8000}"

cd "$PROJECT_ROOT"

echo "Serving dashboard at http://localhost:${PORT}/"
echo "Press Ctrl+C to stop."

python3 -m http.server "$PORT" --bind 127.0.0.1
