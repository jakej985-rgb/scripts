#!/bin/bash

set -e

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[INIT] Running self-healing setup..."

# Required directories
DIRS=(
  "$BASE_DIR/control-plane/state"
  "$BASE_DIR/control-plane/state/logs"
  "$BASE_DIR/control-plane/state/tmp"
  "$BASE_DIR/control-plane/agents"
)

for dir in "${DIRS[@]}"; do
  if [ ! -d "$dir" ]; then
    echo "[INIT] Creating missing dir: $dir"
    mkdir -p "$dir"
  fi
done

# Required log files
LOGS=(
  "$BASE_DIR/control-plane/state/logs/loop.log"
  "$BASE_DIR/control-plane/state/logs/metrics.log"
  "$BASE_DIR/control-plane/state/logs/anomaly.log"
)

for file in "${LOGS[@]}"; do
  if [ ! -f "$file" ]; then
    echo "[INIT] Creating missing log: $file"
    touch "$file"
  fi
done

# Fix permissions (important for Docker + mounted drives)
chmod -R 775 "$BASE_DIR/control-plane/state"

echo "[INIT] Done."
