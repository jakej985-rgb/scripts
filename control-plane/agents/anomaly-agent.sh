#!/bin/bash
# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT

# ANOMALY AGENT
# Detects exited containers or issues from state.json

STATE="$REPO_ROOT/control-plane/state"
IN="$STATE/state.json"
OUT="$STATE/anomalies.json"

> $OUT

if [ ! -f "$IN" ]; then exit 0; fi

# Process state.json using jq
# state.json is a sequence of JSON objects (one per container)
cat "$IN" | jq -c '.' | while read -r line; do
  name=$(echo "$line" | jq -r '.Names')
  state=$(echo "$line" | jq -r '.State')
  status=$(echo "$line" | jq -r '.Status')

  if [ "$state" = "exited" ]; then
    echo "{\"service\": \"$name\", \"issue\": \"exited\", \"detail\": \"$status\"}" >> $OUT
  elif echo "$status" | grep -qi "restarting"; then
    echo "{\"service\": \"$name\", \"issue\": \"crash_loop\", \"detail\": \"restarting\"}" >> $OUT
  fi
done
