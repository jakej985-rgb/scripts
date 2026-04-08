#!/bin/bash

# metrics.sh - Collects cluster-wide node metrics

BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CLUSTER="$BASE_DIR/control-plane/config/cluster.yml"
METRICS="$BASE_DIR/control-plane/state/metrics.json"

echo "{" > "${METRICS}.tmp"

nodes=$(yq e '.nodes | keys | .[]' "$CLUSTER")
count=$(echo "$nodes" | wc -w)
i=0

# Helper to calculate CPU on linux from /proc/stat
CPU_CMD="grep 'cpu ' /proc/stat | awk '{print (\$2+\$4)*100/(\$2+\$4+\$5)}'"

for node in $nodes; do
  host=$(yq e ".nodes.$node.host" "$CLUSTER")
  
  if [ "$host" = "localhost" ]; then
    cpu=$(eval "$CPU_CMD" 2>/dev/null)
  else
    cpu=$(ssh -o ConnectTimeout=2 "$host" "$CPU_CMD" 2>/dev/null)
  fi

  # Fallback if metrics fail
  if [ -z "$cpu" ]; then cpu=0; fi

  i=$((i+1))
  comma=","
  if [ $i -eq $count ]; then comma=""; fi

  echo "  \"$node\": { \"cpu\": $cpu }$comma" >> "${METRICS}.tmp"
done

echo "}" >> "${METRICS}.tmp"
mv "${METRICS}.tmp" "$METRICS"
