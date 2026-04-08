#!/bin/bash

# ANOMALY AGENT - Detects abnormal conditions
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$BASE_DIR/control-plane/state/logs/anomaly-agent.log"
IN="$BASE_DIR/control-plane/state/metrics.json" # Container states
METRICS_IN="$BASE_DIR/control-plane/state/normalized_metrics.json" # CPU metrics
OUT="$BASE_DIR/control-plane/state/anomalies.json"

echo "[ANOMALY] $(date)" >> "$LOG"
# Empty anomalies list to start fresh
echo "" > "${OUT}.tmp"

if [ ! -f "$IN" ]; then exit 0; fi

# Detect Exited Containers from metrics.json (Raw Docker PS data)
cat "$IN" | jq -c '.' | while read -r line; do
  name=$(echo "$line" | jq -r '.Names')
  state=$(echo "$line" | jq -r '.State')
  status=$(echo "$line" | jq -r '.Status')

  if [ "$state" = "exited" ]; then
    echo "{\"service\": \"$name\", \"issue\": \"exited\", \"detail\": \"$status\"}" >> "$OUT.tmp"
  elif echo "$status" | grep -qi "restarting"; then
    echo "{\"service\": \"$name\", \"issue\": \"crash_loop\", \"detail\": \"restarting\"}" >> "$OUT.tmp"
  fi
done

# Detect High CPU (Threshold 80%) from Normalized Metrics
if [ -f "$METRICS_IN" ]; then
    nodes=$(jq -r 'keys[]' "$METRICS_IN")
    for node in $nodes; do
        cpu=$(jq -r ".$node.cpu" "$METRICS_IN")
        if (( $(echo "$cpu > 80" | bc -l) )); then
            echo "{\"service\": \"node:$node\", \"issue\": \"high_cpu\", \"detail\": \"$cpu%\"}" >> "$OUT.tmp"
        fi
    done
fi

# Clean up empty lines and finalize
sed -i '/^$/d' "${OUT}.tmp"
mv "${OUT}.tmp" "$OUT"
