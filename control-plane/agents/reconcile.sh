#!/bin/bash

CLUSTER="control-plane/config/cluster.yml"
LOG="control-plane/state/logs/reconcile.log"

echo "[RECONCILE] $(date)" >> $LOG

running=$(docker ps --format "{{.Names}}")
defined=$(yq e '.services | keys | .[]' $CLUSTER)

# --- enforce desired services ---
for svc in $defined; do
  enabled=$(yq e ".services.$svc.enabled" $CLUSTER)
  stack=$(yq e ".services.$svc.stack" $CLUSTER)

  if [ "$enabled" = "true" ]; then
    if ! echo "$running" | grep -q "^$svc$"; then
      echo "[START] $svc via $stack" | tee -a $LOG
      bash scripts/docker-exec.sh $stack
    else
      status=$(docker inspect --format='{{.State.Health.Status}}' $svc 2>/dev/null)
      if [ "$status" = "unhealthy" ]; then
        echo "[HEAL] $svc unhealthy → restarting" | tee -a $LOG
        docker restart $svc
      fi
    fi
  else
    if echo "$running" | grep -q "^$svc$"; then
      echo "[STOP] $svc disabled" | tee -a $LOG
      docker stop $svc
    fi
  fi
done

# --- remove unknown containers (strict mode optional) ---
for c in $running; do
  if ! echo "$defined" | grep -q "^$c$"; then
    echo "[WARN] Unknown container: $c" | tee -a $LOG
  fi
done

echo "[RECONCILE DONE]" >> $LOG
