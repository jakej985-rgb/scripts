#!/bin/bash

CLUSTER="control-plane/config/cluster.yml"
LOG="control-plane/state/logs/reconcile.log"

echo "[RECONCILE] $(date)" >> $LOG

defined=$(yq e '.services | keys | .[]' $CLUSTER)
running=$(docker ps --format "{{.Names}}")

# --- enforce desired services ---
for svc in $defined; do
  enabled=$(yq e ".services.$svc.enabled" $CLUSTER)
  stack=$(yq e ".services.$svc.stack" $CLUSTER)

  if [ "$enabled" = "true" ]; then

    # --- MISSING ---
    if ! echo "$running" | grep -q "^$svc$"; then
      echo "[START] $svc via $stack" | tee -a $LOG
      bash scripts/docker-exec.sh $stack
      continue
    fi

    # --- HEALTH CHECK ---
    status=$(docker inspect --format='{{.State.Health.Status}}' $svc 2>/dev/null)

    if [ "$status" = "unhealthy" ]; then
      echo "[HEAL] $svc unhealthy → restart" | tee -a $LOG
      docker restart $svc
    fi

  else
    # --- DISABLED SERVICE ---
    if echo "$running" | grep -q "^$svc$"; then
      echo "[STOP] $svc disabled" | tee -a $LOG
      docker stop $svc
    fi
  fi
done

# --- DETECT DRIFT ---
for c in $running; do
  if ! echo "$defined" | grep -q "^$c$"; then
    echo "[DRIFT] Unknown container: $c" | tee -a $LOG
  fi
done

echo "[RECONCILE DONE]" >> $LOG
