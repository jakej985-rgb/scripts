#!/bin/bash
# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT

STATE="$REPO_ROOT/control-plane/state"
ANOM="$STATE/anomalies.json"
OUT="$STATE/decisions.json"

> $OUT

if [ ! -f "$ANOM" ]; then
  echo "{\"actions\": []}" > $OUT
  exit 0
fi

has_anomalies=$(wc -c < "$ANOM")
if [ "$has_anomalies" -eq 0 ]; then
  echo "{\"actions\": []}" > $OUT
  exit 0
fi

echo "{\"actions\": [" > $OUT
first=true

cat "$ANOM" | jq -c '.' | while read -r line; do
  svc=$(echo "$line" | jq -r '.service')
  issue=$(echo "$line" | jq -r '.issue')

  if [ "$issue" = "exited" ] || [ "$issue" = "crash_loop" ]; then
    if [ "$first" = true ]; then
      first=false
    else
      echo "," >> $OUT
    fi
    echo "    {\"service\": \"$svc\", \"action\": \"restart\"}" >> $OUT
  fi
done

echo "  ]" >> $OUT
echo "}" >> $OUT
