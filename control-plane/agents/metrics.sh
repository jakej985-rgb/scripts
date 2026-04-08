#!/bin/bash

# METRICS AGENT - Normalizes and aggregates metrics
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$BASE_DIR/control-plane/state/logs/metrics.log"
IN="$BASE_DIR/control-plane/state/metrics.json"
OUT="$BASE_DIR/control-plane/state/normalized_metrics.json"
CLUSTER="$BASE_DIR/control-plane/config/cluster.yml"

echo "[METRICS] $(date)" >> "$LOG"
echo "{" > "${OUT}.tmp"

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

  echo "  \"$node\": { \"cpu\": $cpu }$comma" >> "${OUT}.tmp"
done

echo "}" >> "${OUT}.tmp"
mv "${OUT}.tmp" "$OUT"
