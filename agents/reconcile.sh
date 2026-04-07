#!/bin/bash

# 🔄 Reconcile Agent v7 — Declarative State Enforcement
# Compares desired state (cluster.yml) against actual state
# Scales up/down to match, respects cooldowns

CONFIG="/docker/config/cluster.yml"
STATE="/docker/state"
LOG="/docker/logs/reconcile.log"

if [ ! -f "$CONFIG" ]; then exit 0; fi

LOCK="$STATE/locks/reconcile.lock"
[ -f "$LOCK" ] && exit 0
trap "rm -f $LOCK" EXIT
touch "$LOCK"

# Check if yq is available
if ! command -v yq &>/dev/null; then
  exit 0
fi

COOLDOWN_DIR="$STATE/cooldowns"

yq e '.services | keys | .[]' "$CONFIG" 2>/dev/null | while read SERVICE; do
  IMAGE=$(yq e ".services.$SERVICE.image" "$CONFIG")
  REPLICAS=$(yq e ".services.$SERVICE.replicas // 1" "$CONFIG")
  NODE=$(yq e ".services.$SERVICE.node // \"local\"" "$CONFIG")

  # Skip if targeted at a different node
  if [ "$NODE" != "local" ] && [ "$NODE" != "auto" ] && [ "$NODE" != "$(hostname)" ]; then
    continue
  fi

  # Count current instances (main + replicas)
  CURRENT=$(docker ps --filter "name=$SERVICE" --format "{{.Names}}" 2>/dev/null | wc -l)

  # Cooldown (3 min between reconcile actions per service)
  RECONCILE_CD="$COOLDOWN_DIR/reconcile_${SERVICE}"
  if [ -f "$RECONCILE_CD" ] && [ $(($(date +%s) - $(cat "$RECONCILE_CD"))) -lt 180 ]; then
    continue
  fi

  # Scale UP to match desired
  if [ "$CURRENT" -lt "$REPLICAS" ]; then
    NEEDED=$((REPLICAS - CURRENT))
    for i in $(seq 1 $NEEDED); do
      REPLICA_NUM=$((CURRENT + i))
      NEW_NAME="${SERVICE}-replica-${REPLICA_NUM}"
      # Check if this replica already exists (stopped)
      if docker ps -a --format "{{.Names}}" 2>/dev/null | grep -q "^${NEW_NAME}$"; then
        docker start "$NEW_NAME" 2>/dev/null
        echo "$(date) RECONCILE: started existing $NEW_NAME" >> "$LOG"
      else
        docker run -d --name "$NEW_NAME" --restart unless-stopped "$IMAGE" 2>/dev/null
        echo "$(date) RECONCILE: created $NEW_NAME ($IMAGE)" >> "$LOG"
      fi
    done
    date +%s > "$RECONCILE_CD"
  fi

  # Scale DOWN to match desired
  if [ "$CURRENT" -gt "$REPLICAS" ]; then
    EXCESS=$((CURRENT - REPLICAS))
    # Only remove replicas, never the original
    docker ps --filter "name=${SERVICE}-replica" --format "{{.Names}}" 2>/dev/null | tail -n "$EXCESS" | while read VICTIM; do
      docker stop "$VICTIM" 2>/dev/null
      docker rm "$VICTIM" 2>/dev/null
      echo "$(date) RECONCILE: removed $VICTIM" >> "$LOG"
    done
    date +%s > "$RECONCILE_CD"
  fi
done
