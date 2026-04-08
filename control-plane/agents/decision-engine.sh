#!/bin/bash

# DECISION ENGINE - Determines corrective actions
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$BASE_DIR/control-plane/state/logs/decision-engine.log"
ANOM="$BASE_DIR/control-plane/state/anomalies.json"
OUT="$BASE_DIR/control-plane/state/decisions.json"

echo "[DECISION] $(date)" >> "$LOG"

if [ ! -f "$ANOM" ] || [ ! -s "$ANOM" ]; then
  echo "{\"actions\": []}" > "$OUT"
  exit 0
fi

echo "{\"actions\": [" > "$OUT.tmp"
first=true

while read -r line; do
  [ -z "$line" ] && continue
  svc=$(echo "$line" | jq -r '.service')
  issue=$(echo "$line" | jq -r '.issue')

  if [ "$issue" = "exited" ] || [ "$issue" = "crash_loop" ]; then
    [ "$first" = true ] && first=false || echo "," >> "$OUT.tmp"
    echo "    {\"service\": \"$svc\", \"action\": \"restart\"}" >> "$OUT.tmp"
  elif [ "$issue" = "high_cpu" ]; then
    [ "$first" = true ] && first=false || echo "," >> "$OUT.tmp"
    echo "    {\"service\": \"$svc\", \"action\": \"scale_up\"}" >> "$OUT.tmp"
  fi
done < "$ANOM"

echo "  ]" >> "$OUT.tmp"
echo "}" >> "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
