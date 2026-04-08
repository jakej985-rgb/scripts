#!/bin/bash

# HA-leader.sh - Distributed Leader Election (Minimalist Raft-like behavior)
# >>> AUTO-ROOT (antigravity)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT

CLUSTER="$REPO_ROOT/control-plane/config/cluster.yml"
STATE_DIR="$REPO_ROOT/control-plane/state"
LEADER_FILE="$STATE_DIR/leader.txt"
MY_NODE=$(hostname) 

# 1. Identify all eligible control nodes
CONTROL_NODES=$(yq e '.nodes | with_entries(select(.value.role == "control")) | keys | .[]' "$CLUSTER")

for node in $CONTROL_NODES; do
    host=$(yq e ".nodes.$node.host" "$CLUSTER")
    
    # HIGH-06: Fix leader election — use proper reachability checks
    if [ "$host" = "localhost" ]; then
        echo "$node" > "$LEADER_FILE"
        break
    else
        ip=$(echo "$host" | cut -d'@' -f2 | cut -d':' -f1)
        if ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then
            echo "$node" > "$LEADER_FILE"
            break
        fi
    fi
done

CURRENT_LEADER=$(cat "$LEADER_FILE" 2>/dev/null || echo "")
if [ "$CURRENT_LEADER" != "$MY_NODE" ] && [[ "$MY_NODE" != "localhost"* ]]; then
    echo "[HA] I am Follower. Leader is $CURRENT_LEADER"
    exit 1 
else
    echo "[HA] I am LEADER ($CURRENT_LEADER). Executing pipeline."
    exit 0 
fi
