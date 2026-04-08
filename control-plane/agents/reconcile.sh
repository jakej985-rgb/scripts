#!/bin/bash

# RECONCILE AGENT - Enforcer as per Task 6
# Reads decisions.json (actions) and registry.json (source of truth)

# >>> AUTO-ROOT (antigravity)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT

STATE_DIR="$REPO_ROOT/control-plane/state"
LOG="$STATE_DIR/logs/reconcile.log"
DECISIONS="$STATE_DIR/decisions.json"
REGISTRY="$STATE_DIR/registry.json"

echo "-----------------------------------" >> "$LOG"
echo "[RECONCILE] $(date)" >> "$LOG"

# 1. Pipeline Check
if [ ! -f "$DECISIONS" ]; then
    echo "[SKIPPED] Missing decisions.json" >> "$LOG"
    exit 0
fi

# 2. Process Actions (Task 6)
actions=$(jq -c '.actions[]' "$DECISIONS" 2>/dev/null)

if [ -z "$actions" ]; then
    echo "[IDLE] No actions requested." >> "$LOG"
else
    echo "[EXECUTE] Processing actions..." >> "$LOG"
    echo "$actions" | while read -r action; do
        type=$(echo "$action" | jq -r '.type')
        target=$(echo "$action" | jq -r '.target')
        reason=$(echo "$action" | jq -r '.reason')
        
        echo "[ACTION] Performing $type on $target (Reason: $reason)" | tee -a "$LOG"
        
        case "$type" in
            "restart")
                docker restart "$target" >> "$LOG" 2>&1
                ;;
            "start")
                docker start "$target" >> "$LOG" 2>&1
                ;;
            "stop")
                docker stop "$target" >> "$LOG" 2>&1
                ;;
            *)
                echo "[WARN] Unknown action type: $type" >> "$LOG"
                ;;
        esac
    done
    
    # Clear decisions after execution to ensure idempotency
    echo '{"actions": []}' > "$DECISIONS"
fi

# 3. Storage Enforcement (CRITICAL - AGENT_PLAN.md)
# Ensure all managed containers use /mnt:/mnt
if [ -f "$REGISTRY" ]; then
    containers=$(jq -r '.containers[]' "$REGISTRY")
    for c in $containers; do
        mounts=$(docker inspect "$c" --format='{{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}' 2>/dev/null)
        if [[ ! "$mounts" =~ "/mnt:/mnt" ]]; then
            echo "[VIOLATION] $c missing /mnt:/mnt mount!" >> "$LOG"
            # In a fully autonomous system, we might recreate the container here.
            # For now, we log the violation as per "deterministic" requirement.
        fi
    done
fi

echo "[DONE] Reconciliation cycle complete." >> "$LOG"