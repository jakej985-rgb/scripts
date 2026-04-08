#!/bin/bash

# run-orchestrator.sh
# Phase 2: Fix control loop reliability with per-agent execution wrapper

set -e
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$BASE_DIR/control-plane/state/logs/loop.log"
HEALTH_FILE="$BASE_DIR/control-plane/state/agent-health.json"

# 1. Initialize System
echo "[RUN] Bootstrapping pipeline..."
bash "$BASE_DIR/control-plane/init.sh"

function run_agent() {
    local name=$1
    local cmd=$2
    local start_time=$(date +%s)
    
    echo "[$(date '+%H:%M:%S')] Executing $name..." >> "$LOG_FILE"
    
    # Phase 5: Watchdog Check
    # (Simple version: skip if agent-health says failing AND last failure < 60s ago)
    if [ -f "$HEALTH_FILE" ] && command -v jq >/dev/null 2>&1; then
        local status=$(jq -r ".[\"$name\"].status" "$HEALTH_FILE")
        local last_fail=$(jq -r ".[\"$name\"].last_failure" "$HEALTH_FILE")
        local now=$(date +%s)
        if [ "$status" == "failing" ] && [ $((now - last_fail)) -lt 60 ]; then
            echo "[WATCHDOG] Skipping $name (unstable, cooling down)" >> "$LOG_FILE"
            return 0
        fi
    fi

    # Execute with 60s timeout
    if eval "timeout 60s python3 $cmd" >> "$LOG_FILE" 2>&1; then
        echo "  ✔ $name success" >> "$LOG_FILE"
    else
        echo "  ✖ $name failed in $(( $(date +%s) - start_time ))s" >> "$LOG_FILE"
        # We short-circuit only on critical perception failure if needed
        # but here we follow Rule #2: loop continues
    fi
}

echo "[RUN] Entering hardened control loop..."

while true; do
    echo "--- Loop Start: $(date) ---" >> "$LOG_FILE"
    
    # HA Gate
    if [ -f "$BASE_DIR/control-plane/agents/ha-leader.sh" ]; then
        if ! bash "$BASE_DIR/control-plane/agents/ha-leader.sh" >> "$LOG_FILE" 2>&1; then
            sleep 10; continue
        fi
    fi

    # Pipeline Phase 1: Perception
    run_agent "monitor" "$BASE_DIR/control-plane/agents/monitor.py"
    run_agent "metrics" "$BASE_DIR/control-plane/agents/metrics.py"
    
    # Pipeline Phase 2: Analysis
    run_agent "anomaly" "$BASE_DIR/control-plane/agents/anomaly.py"
    run_agent "decision" "$BASE_DIR/control-plane/agents/decision.py"
    
    # Pipeline Phase 3: Execution
    echo "[$(date '+%H:%M:%S')] Executing reconcile..." >> "$LOG_FILE"
    bash "$BASE_DIR/control-plane/agents/reconcile.sh" >> "$LOG_FILE" 2>&1 || echo "  ✖ reconcile failed" >> "$LOG_FILE"
    
    # Pipeline Phase 4: Routing
    run_agent "registry" "$BASE_DIR/control-plane/agents/registry.py"

    sleep 10
done