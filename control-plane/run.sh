#!/bin/bash

set -e
# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# <<< AUTO-ROOT

echo "[RUN] Starting control plane..."

# -----------------------------
# Self-heal first
# -----------------------------
bash "$REPO_ROOT/control-plane/init.sh"

LOG_FILE="$REPO_ROOT/control-plane/state/logs/loop.log"
LEADER_FILE="$REPO_ROOT/control-plane/state/leader.txt"

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
  for agent in path-agent monitor metrics anomaly-agent decision-engine reconcile registry; do
    SCRIPT="$REPO_ROOT/control-plane/agents/$agent.sh"

    if [ -f "$SCRIPT" ]; then
      echo "[RUN] Executing $agent" >> "$LOG_FILE"
      bash "$SCRIPT" >> "$LOG_FILE" 2>&1 || echo "[ERROR] $agent failed" >> "$LOG_FILE"
    else
      echo "[WARN] Missing $SCRIPT" >> "$LOG_FILE"
    fi
  done

  sleep 10
done