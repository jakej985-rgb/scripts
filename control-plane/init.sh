#!/bin/bash

set -e
# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# <<< AUTO-ROOT

echo "[INIT] Running self-healing setup..."

# -----------------------------
# Directories
# -----------------------------
DIRS=(
  "$REPO_ROOT/control-plane/state"
  "$REPO_ROOT/control-plane/state/logs"
  "$REPO_ROOT/control-plane/state/tmp"
  "$REPO_ROOT/control-plane/agents"
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
  "$REPO_ROOT/control-plane/state/logs/loop.log"
  "$REPO_ROOT/control-plane/state/logs/metrics.log"
  "$REPO_ROOT/control-plane/state/logs/anomaly.log"
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
LEADER_FILE="$REPO_ROOT/control-plane/state/leader.txt"

if [ ! -f "$LEADER_FILE" ]; then
  echo "[INIT] Creating leader file"
  touch "$LEADER_FILE"
  echo "none" > "$LEADER_FILE"
fi

# -----------------------------
# Optional permissions (safe)
# -----------------------------
chmod -R 775 "$REPO_ROOT/control-plane/state" 2>/dev/null || true

echo "[INIT] Done."