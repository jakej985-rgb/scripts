#!/bin/bash

STATE="/docker/state"
ACTIONS="$STATE/actions.txt"
> $ACTIONS

LOCK="$STATE/locks/decision.lock"

[ -f "$LOCK" ] && exit 0
trap "rm -f $LOCK" EXIT
touch $LOCK

# ── Process analyzer findings ──
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

# ── v3.1: Process anomaly detections ──
if [ -f "$STATE/anomalies.txt" ]; then
  while read line; do
    NAME=$(echo $line | awk '{print $1}')
    ISSUE=$(echo $line | awk '{print $2}')
    VALUE=$(echo $line | awk '{print $3}')

    if [ "$ISSUE" == "HIGH_CPU" ]; then
      echo "$NAME ALERT_CPU $VALUE" >> $ACTIONS
    fi

    if [ "$ISSUE" == "HIGH_MEM" ]; then
      echo "$NAME ALERT_MEM $VALUE" >> $ACTIONS
    fi

  done < $STATE/anomalies.txt
fi

# ── v3.2: Process dependency issues ──
if [ -f "$STATE/dependency-issues.txt" ]; then
  while read line; do
    APP=$(echo $line | awk '{print $1}')
    TYPE=$(echo $line | awk '{print $2}')
    DEP=$(echo $line | awk '{print $3}')

    echo "$APP ALERT_DEP_${TYPE} $DEP" >> $ACTIONS
  done < $STATE/dependency-issues.txt
fi

# ── v3: Process AI recommendations (safe + bounded) ──
if [ -f "$STATE/ai-recommendations.txt" ]; then
  if grep -qi "restart" "$STATE/ai-recommendations.txt"; then
    NAMES=$(grep -i "restart" "$STATE/ai-recommendations.txt" | grep -oP '\b[a-z][\w-]+\b' | sort -u)
    for N in $NAMES; do
      if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${N}$"; then
        echo "$N RESTART_SUGGESTED" >> $ACTIONS
      fi
    done
  fi
fi

bash /docker/agents/action-agent.sh
