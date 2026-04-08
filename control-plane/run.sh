#!/bin/bash

# M3TAL Supervisor - Reliable Control Plane Launcher
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
  
  # Tracking for backoff (Batch 3 T6)
  local crash_count=0
  local last_crash=0

  while true; do
    echo "[$(date '+%H:%M:%S')] Starting $name..."
    if [ "$interpreter" == "python" ]; then
        python3 "$script" >> "$LOG_DIR/$name.log" 2>&1
    else
        bash "$script" >> "$LOG_DIR/$name.log" 2>&1
    fi

    exit_code=$?
    now=$(date +%s)
    
    if [ $exit_code -eq 0 ]; then
        crash_count=0 # Reset on success
        sleep 2
    else
        # Backoff logic
        ((crash_count++))
        wait_time=$(( 5 * crash_count ))
        [ $wait_time -gt 60 ] && wait_time=60 # Cap at 60s
        
        echo "[$(date '+%H:%M:%S')] CRASH: $name (Count: $crash_count). Restarting in ${wait_time}s..."
        sleep "$wait_time"
    fi
  done
}

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
run_agent chaos "$BASE_DIR/agents/chaos_test.py" python &

echo "[$(date '+%H:%M:%S')] All agents running."
wait