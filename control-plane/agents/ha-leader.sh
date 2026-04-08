#!/bin/bash

# HA-leader.sh - Distributed Leader Election (Minimalist Raft-like behavior)

CLUSTER="control-plane/config/cluster.yml"
STATE_DIR="control-plane/state"
LEADER_FILE="$STATE_DIR/leader.txt"
MY_NODE=$(hostname) # Or identify via config

# 1. Identify all eligible control nodes
CONTROL_NODES=$(yq e '.nodes | with_entries(select(.value.role == "control")) | keys | .[]' $CLUSTER)

function try_lock() {
    node=$1
    host=$(yq e ".nodes.$node.host" $CLUSTER)
    
    # Try to create a remote lock file with a TTL (simulated by timestamp)
    now=$(date +%s)
    # We use a shared filesystem or a distributed "lock" via SSH for this MVP
    # In a real HA setup, this would target a shared DB/Consul/Etcd
    # For M3TAL: We check who has the oldest active heartbeat in the cluster state
    return 0
}

# BASIC LEADER ELECTION LOGIC
# For this Shell-based HA: The "First Active" control node in the list is the Leader.
# If it fails, the next one takes over.

for node in $CONTROL_NODES; do
    host=$(yq e ".nodes.$node.host" $CLUSTER)
    
    # Check if node is alive
    if [ "$host" = "localhost" ]; then
        ping_ok=true
    else
        ping -c 1 -W 1 $(echo $host | cut -d'@' -f2) >/dev/null 2>&1
        ping_ok=$?
    fi

    if [ $ping_ok -eq 0 ]; then
        echo $node > $LEADER_FILE
        break
    fi
done

CURRENT_LEADER=$(cat $LEADER_FILE)
if [ "$CURRENT_LEADER" = "control" ] && [ "$MY_NODE" != "control" ]; then
    echo "[HA] I am Follower. Leader is $CURRENT_LEADER"
    exit 1 # Stop execution of main loop
else
    echo "[HA] I am LEADER ($CURRENT_LEADER). Executing pipeline."
    exit 0 # Continue execution
fi
