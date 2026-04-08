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
  # HA Gate
  # -----------------------------
  if [ -f "$BASE_DIR/control-plane/agents/ha-leader.sh" ]; then
    if ! bash "$BASE_DIR/control-plane/agents/ha-leader.sh"; then
      sleep 10
      continue
    fi
  fi

  # -----------------------------
  # Agent execution (Hybrid Python/Bash)
  # -----------------------------
  
  # 1. Perception Layer (Python)
  python3 "$BASE_DIR/control-plane/python/monitor.py" >> "$LOG_FILE" 2>&1
  python3 "$BASE_DIR/control-plane/python/metrics.py" >> "$LOG_FILE" 2>&1
  
  # 2. Analysis Layer (Python)
  python3 "$BASE_DIR/control-plane/python/anomaly.py" >> "$LOG_FILE" 2>&1
  python3 "$BASE_DIR/control-plane/python/decision.py" >> "$LOG_FILE" 2>&1
  
  # 3. Execution Layer (Bash - Critical System Commands)
  bash "$BASE_DIR/control-plane/agents/reconcile.sh" >> "$LOG_FILE" 2>&1
  
  # 4. Routing Layer (Python)
  python3 "$BASE_DIR/control-plane/python/registry.py" >> "$LOG_FILE" 2>&1

  sleep 10
done