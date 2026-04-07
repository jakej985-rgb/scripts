#!/bin/bash

LOG="control-plane/state/logs/reconcile.log"
STRICT=false

# =========================
# LOAD STATE
# =========================
CLUSTER="control-plane/config/cluster.yml"
running=$(docker ps --format "{{.Names}}")
defined=$(yq e '.services | keys | .[]' $CLUSTER)

echo "[RECONCILE] $(date)" >> $LOG

# =========================
# SERVICE ENFORCEMENT
# =========================
for svc in $defined; do
  enabled=$(yq e ".services.$svc.enabled" $CLUSTER)
  stack=$(yq e ".services.$svc.stack" $CLUSTER)
  replicas=$(yq e ".services.$svc.replicas" $CLUSTER)
  if [ "$replicas" = "null" ] || [ -z "$replicas" ]; then replicas=1; fi

  autoscale=$(yq e ".services.$svc.autoscale.enabled" $CLUSTER)
  cpu_threshold=$(yq e ".services.$svc.autoscale.cpu_threshold" $CLUSTER)
  max=$(yq e ".services.$svc.autoscale.max" $CLUSTER)
  min=$(yq e ".services.$svc.autoscale.min" $CLUSTER)

  containers=$(echo "$running" | grep "^$svc")
  count=$(echo "$containers" | grep -c "^$svc")

  # CPU-based Auto Scale Decision
  if [ "$autoscale" = "true" ]; then
    cpu=$(grep "^$svc" control-plane/state/metrics.txt | awk '{print $2}' | tr -d '%')
    if [ -n "$cpu" ]; then
      if (( $(echo "$cpu > $cpu_threshold" | bc -l) )) && [ "$count" -lt "$max" ]; then
        echo "[AUTO-SCALE-UP] $svc cpu=$cpu%" | tee -a $LOG
        replicas=$(($count + 1))
      fi

      if (( $(echo "$cpu < 30" | bc -l) )) && [ "$count" -gt "$min" ]; then
        echo "[AUTO-SCALE-DOWN] $svc cpu=$cpu%" | tee -a $LOG
        replicas=$(($count - 1))
      fi
    fi
  fi

  # 1. Disabled handling FIRST
  if [ "$enabled" != "true" ]; then
    if [ "$count" -gt 0 ]; then
      for c in $containers; do
        if [ -n "$c" ]; then
          echo "[STOP] $c disabled" | tee -a $LOG
          docker stop $c
        fi
      done
    fi
    continue
  fi

  # 2. Existence check
  if [ "$count" -eq 0 ]; then
    echo "[START] $svc via $stack" | tee -a $LOG
    bash scripts/docker-exec.sh $stack
    continue
  fi

  # =========================
  # SCALING
  # =========================
  if [ "$count" -lt "$replicas" ]; then
    echo "[SCALE-UP] $svc ($count -> $replicas)" | tee -a $LOG

    missing=$(($replicas - $count))

    for i in $(seq 1 $missing); do
      name="$svc-$((count + i))"

      echo "[CREATE] $name from $stack" | tee -a $LOG

      docker compose -f docker/$stack/docker-compose.yml run -d --name $name $svc
    done
  fi

  if [ "$count" -gt "$replicas" ]; then
    echo "[SCALE-DOWN] $svc ($count -> $replicas)" | tee -a $LOG

    extras=$(echo "$containers" | tail -n +$(($replicas + 1)))

    for c in $extras; do
      if [ -n "$c" ]; then
        echo "[REMOVE] $c" | tee -a $LOG
        docker stop $c
        docker rm $c
      fi
    done
  fi

  # =========================
  # HEALTH CHECKS
  # =========================
  for c in $containers; do
    if [ -n "$c" ]; then
      status=$(docker inspect --format='{{.State.Health.Status}}' $c 2>/dev/null)
      if [ "$status" = "unhealthy" ]; then
        echo "[HEAL] $c unhealthy → restart" | tee -a $LOG
        docker restart $c
      fi
    fi
  done

done

# =========================
# DRIFT DETECTION
# =========================
for c in $running; do
  if ! echo "$defined" | grep -q "^$c$"; then
    echo "[DRIFT] Unknown container: $c" | tee -a $LOG
    if [ "$STRICT" = "true" ]; then
      docker stop $c
    fi
  fi
done

# =========================
# SUMMARY
# =========================
def_count=$(echo "$defined" | wc -w)
run_count=$(echo "$running" | wc -w)
echo "[SUMMARY] services=$def_count running=$run_count" >> $LOG
echo "[RECONCILE DONE]" >> $LOG
