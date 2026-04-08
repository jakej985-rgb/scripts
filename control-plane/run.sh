#!/bin/bash

# M3TAL Supervisor - Reliable Control Plane Launcher
# Follows AGENT_PLAN.md Supervisor Model

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="$BASE_DIR/state"
LOG_DIR="$STATE_DIR/logs"

mkdir -p "$LOG_DIR"

# Ensure initialization runs first
bash "$BASE_DIR/init.sh"

run_agent() {
  local name=$1
  local script=$2
  local interpreter=$3

  while true; do
    echo "[$(date '+%H:%M:%S')] Starting $name..."
    if [ "$interpreter" == "python" ]; then
        python3 "$script" >> "$LOG_DIR/$name.log" 2>&1
    else
        bash "$script" >> "$LOG_DIR/$name.log" 2>&1
    fi

    echo "[$(date '+%H:%M:%S')] CRASH: $name exited. Restarting in 5s..."
    sleep 5
  done
}

# Launching agents in background
echo "[$(date '+%H:%M:%S')] Supervisor launching Agents..."

run_agent monitor "$BASE_DIR/agents/monitor.py" python &
run_agent metrics "$BASE_DIR/agents/metrics.py" python &
run_agent anomaly "$BASE_DIR/agents/anomaly.py" python &
run_agent decision "$BASE_DIR/agents/decision.py" python &
run_agent reconcile "$BASE_DIR/agents/reconcile.sh" bash &
run_agent registry "$BASE_DIR/agents/registry.py" python &

# Observer and Scorer (Phase 3 context)
run_agent observer "$BASE_DIR/agents/recovery_check.py" python &
run_agent scorer "$BASE_DIR/agents/health_score.py" python &

echo "[$(date '+%H:%M:%S')] All agents running. Supervisor waiting..."

wait