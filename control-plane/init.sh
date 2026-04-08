#!/bin/bash

set -e

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[INIT] Running self-healing setup..."

# -----------------------------
# Directories
# -----------------------------
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

# -----------------------------
# Log files
# -----------------------------
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

# -----------------------------
# Leader file (YOUR FIX)
# -----------------------------
LEADER_FILE="$BASE_DIR/control-plane/state/leader.txt"

if [ ! -f "$LEADER_FILE" ]; then
  echo "[INIT] Creating leader file"
  touch "$LEADER_FILE"
  echo "none" > "$LEADER_FILE"
fi

# -----------------------------
# Optional permissions (safe)
# -----------------------------
chmod -R 775 "$BASE_DIR/control-plane/state" 2>/dev/null || true

echo "[INIT] Done."