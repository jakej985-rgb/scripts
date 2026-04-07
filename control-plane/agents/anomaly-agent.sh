#!/bin/bash

# ANOMALY AGENT
# Detects exited containers or issues from state.json

STATE="control-plane/state"
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
