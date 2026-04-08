#!/bin/bash

# HA-leader.sh - Distributed Leader Election (Minimalist Raft-like behavior)
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CLUSTER="$BASE_DIR/control-plane/config/cluster.yml"
STATE_DIR="$BASE_DIR/control-plane/state"
LEADER_FILE="$STATE_DIR/leader.txt"
MY_NODE=$(hostname) 

# 1. Identify all eligible control nodes
CONTROL_NODES=$(yq e '.nodes | with_entries(select(.value.role == "control")) | keys | .[]' "$CLUSTER")

for node in $CONTROL_NODES; do
    host=$(yq e ".nodes.$node.host" "$CLUSTER")
    
    # Check if node is alive
    if [ "$host" = "localhost" ]; then
        ping_ok=0
    else
        ping -c 1 -W 1 $(echo "$host" | cut -d'@' -f2 | cut -d':' -f1) >/dev/null 2>&1
        ping_ok=$?
    fi

    if [ $ping_ok -eq 0 ]; then
        echo "$node" > "$LEADER_FILE"
        break
    fi
done

CURRENT_LEADER=$(cat "$LEADER_FILE")
if [ "$CURRENT_LEADER" != "$MY_NODE" ] && [[ "$MY_NODE" != "localhost"* ]]; then
    # Note: This basic logic needs refinement for specific hostnames,
    # but for now it follows the 'First Active' rule.
    echo "[HA] I am Follower. Leader is $CURRENT_LEADER"
    exit 1 
else
    echo "[HA] I am LEADER ($CURRENT_LEADER). Executing pipeline."
    exit 0 
fi
