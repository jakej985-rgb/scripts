#!/bin/bash

set -e

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[RUN] Starting control plane..."

# -----------------------------
# Self-heal first
# -----------------------------
bash "$BASE_DIR/control-plane/init.sh"

LOG_FILE="$BASE_DIR/control-plane/state/logs/loop.log"
LEADER_FILE="$BASE_DIR/control-plane/state/leader.txt"

# Ensure critical files always exist
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"
touch "$LEADER_FILE"

echo "[RUN] Entering main loop..."

while true; do
  echo "[LOOP] $(date)" >> "$LOG_FILE"

  # -----------------------------
  # Agent execution (safe)
  # -----------------------------
  for agent in monitor metrics anomaly-agent decision-engine reconcile; do
    SCRIPT="$BASE_DIR/control-plane/agents/$agent.sh"

    if [ -f "$SCRIPT" ]; then
      echo "[RUN] Executing $agent" >> "$LOG_FILE"
      bash "$SCRIPT" >> "$LOG_FILE" 2>&1 || echo "[ERROR] $agent failed" >> "$LOG_FILE"
    else
      echo "[WARN] Missing $SCRIPT" >> "$LOG_FILE"
    fi
  done

  sleep 10
done