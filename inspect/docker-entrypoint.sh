#!/usr/bin/env bash
set -euo pipefail

CONFIG_SOURCE=/app/config.js
CONFIG_TARGET=/app/node_modules/csgofloat/config.js

if [ ! -f "$CONFIG_SOURCE" ]; then
  echo "[inspect] Missing config.js. Please create inspect/config.js and mount it into the container." >&2
  echo "You can start from inspect/config.example.js." >&2
  exit 1
fi

mkdir -p "$(dirname "$CONFIG_TARGET")"
cp "$CONFIG_SOURCE" "$CONFIG_TARGET"

exec "$@"
