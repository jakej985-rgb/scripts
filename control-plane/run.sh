#!/bin/bash

# M3TAL Supervisor - Reliable Control Plane Launcher
# Follows AGENT_PLAN.md Supervisor Model

# >>> AUTO-ROOT (antigravity)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# <<< AUTO-ROOT

BASE_DIR="$REPO_ROOT/control-plane"
STATE_DIR="$BASE_DIR/state"
LOG_DIR="$STATE_DIR/logs"

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

    # Exit code check for graceful stops vs crashes
    exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] $name exited normally. Sleeping 2s..."
        sleep 2
    else
        echo "[$(date '+%H:%M:%S')] CRASH: $name exited with $exit_code. Restarting in 5s..."
        sleep 5
    fi
  done
}

# Launching agents in background
echo "[$(date '+%H:%M:%S')] Supervisor launching Agents..."

# Core Pipeline
run_agent registry "$BASE_DIR/agents/registry.py" python &
run_agent monitor "$BASE_DIR/agents/monitor.py" python &
run_agent metrics "$BASE_DIR/agents/metrics.py" python &
run_agent anomaly "$BASE_DIR/agents/anomaly.py" python &
run_agent decision "$BASE_DIR/agents/decision.py" python &
run_agent reconcile "$BASE_DIR/agents/reconcile.py" python &

# Periodic/Maintenance
run_agent scheduler "$BASE_DIR/agents/scheduler.py" python &
run_agent scorer "$BASE_DIR/agents/health_score.py" python &

echo "[$(date '+%H:%M:%S')] All agents running. Supervisor waiting..."

wait