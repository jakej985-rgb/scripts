#!/bin/bash

STATE="/docker/state"
ACTIONS="$STATE/actions.txt"
> $ACTIONS

LOCK="$STATE/locks/decision.lock"

[ -f "$LOCK" ] && exit 0
trap "rm -f $LOCK" EXIT
touch $LOCK

# Process analyzer findings
if [ -f "$STATE/analysis.txt" ]; then
  while read line; do
    NAME=$(echo $line | awk '{print $1}')
    ISSUE=$(echo $line | awk '{print $2}')

    RETRY_FILE="$STATE/retries/$NAME"

    COUNT=0
    [ -f "$RETRY_FILE" ] && COUNT=$(cat $RETRY_FILE)

    if [ "$ISSUE" == "UNHEALTHY" ] && [ "$COUNT" -lt 3 ]; then
      echo "$NAME RESTART" >> $ACTIONS
      echo $((COUNT+1)) > $RETRY_FILE
    elif [ "$ISSUE" == "CRASH_LOOP" ]; then
      echo "$NAME ALERT" >> $ACTIONS
    else
      echo "$NAME ALERT" >> $ACTIONS
    fi

  done < $STATE/analysis.txt
fi

# v3: Process AI recommendations (safe + bounded)
if [ -f "$STATE/ai-recommendations.txt" ]; then
  if grep -qi "restart" "$STATE/ai-recommendations.txt"; then
    # Extract container names mentioned near "restart" (best-effort)
    NAMES=$(grep -i "restart" "$STATE/ai-recommendations.txt" | grep -oP '\b[a-z][\w-]+\b' | sort -u)
    for N in $NAMES; do
      # Only add if it's a real container
      if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${N}$"; then
        echo "$N RESTART_SUGGESTED" >> $ACTIONS
      fi
    done
  fi
fi

bash /docker/agents/action-agent.sh
