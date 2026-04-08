#!/bin/bash

LOG="control-plane/state/logs/loop.log"

echo "[BOOT] $(date)" >> $LOG

while true; do
  # --- HA GATE ---
  bash control-plane/agents/ha-leader.sh || { sleep 20; continue; }

  echo "[LOOP] $(date)" >> $LOG

  bash control-plane/agents/monitor.sh
  bash control-plane/agents/metrics.sh
  bash control-plane/agents/anomaly-agent.sh
  bash control-plane/agents/decision-engine.sh
  bash control-plane/agents/reconcile.sh
  bash control-plane/agents/registry.sh

  sleep 20
done
