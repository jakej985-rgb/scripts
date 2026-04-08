#!/bin/bash

# scheduler.sh - Decides node placement based on least-loaded strategy
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CLUSTER="$BASE_DIR/control-plane/config/cluster.yml"
# Consume the normalized metrics as per plan
METRICS="$BASE_DIR/control-plane/state/normalized_metrics.json"

svc=$1
nodes=$(yq e '.nodes | keys | .[]' "$CLUSTER")

best_node=""
lowest_cpu=999

for node in $nodes; do
  cpu=$(jq -r ".$node.cpu" "$METRICS" 2>/dev/null)
  
  # Default to 0 if metrics are missing
  if [ "$cpu" = "null" ] || [ -z "$cpu" ]; then cpu=0; fi

  if (( $(echo "$cpu < $lowest_cpu" | bc -l) )); then
    lowest_cpu=$cpu
    best_node=$node
  fi
done

echo "$best_node"
