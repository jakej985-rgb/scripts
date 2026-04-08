#!/bin/bash

set -e

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# 🔥 SELF HEAL FIRST
bash "$BASE_DIR/control-plane/init.sh"

LOG_FILE="$BASE_DIR/control-plane/state/logs/loop.log"

# Ensure log exists
[ -f "$LOG_FILE" ] || touch "$LOG_FILE"

echo "[BOOT] $(date)" >> "$LOG_FILE"

while true; do
  # --- HA GATE ---
  bash "$BASE_DIR/control-plane/agents/ha-leader.sh" || { sleep 20; continue; }

  echo "[LOOP] $(date)" >> "$LOG_FILE"

  # Run agents safely
  [ -f "$BASE_DIR/control-plane/agents/monitor.sh" ] && bash "$BASE_DIR/control-plane/agents/monitor.sh"
  [ -f "$BASE_DIR/control-plane/agents/metrics.sh" ] && bash "$BASE_DIR/control-plane/agents/metrics.sh"
  [ -f "$BASE_DIR/control-plane/agents/anomaly-agent.sh" ] && bash "$BASE_DIR/control-plane/agents/anomaly-agent.sh"
  [ -f "$BASE_DIR/control-plane/agents/decision-engine.sh" ] && bash "$BASE_DIR/control-plane/agents/decision-engine.sh"
  [ -f "$BASE_DIR/control-plane/agents/reconcile.sh" ] && bash "$BASE_DIR/control-plane/agents/reconcile.sh"
  [ -f "$BASE_DIR/control-plane/agents/registry.sh" ] && bash "$BASE_DIR/control-plane/agents/registry.sh"

  sleep 20
done
