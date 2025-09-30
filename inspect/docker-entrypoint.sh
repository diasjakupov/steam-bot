#!/usr/bin/env bash
set -euo pipefail

if [ ! -f /app/config.js ]; then
  echo "[inspect] Missing config.js. Please create inspect/config.js and mount it into the container." >&2
  echo "You can start from inspect/config.example.js." >&2
  exit 1
fi

exec "$@"
