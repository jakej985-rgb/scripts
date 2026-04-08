#!/bin/bash

LOG="control-plane/state/logs/reconcile.log"
CLUSTER="control-plane/config/cluster.yml"

echo "[RECONCILE] $(date)" >> $LOG

# =========================
# LOAD NODES + RUNNING STATE
# =========================
nodes=$(yq e '.nodes | keys | .[]' $CLUSTER)
running=""
node_map=""

for node in $nodes; do
  host=$(yq e ".nodes.$node.host" $CLUSTER)

  if [ "$host" = "localhost" ]; then
    node_running=$(docker ps --format "{{.Names}}")
  else
    if ! ping -c 1 -W 1 $(echo $host | cut -d'@' -f2) >/dev/null 2>&1; then
      echo "[NODE DOWN] $node ($host)" | tee -a $LOG
      continue
    fi
    node_running=$(ssh -o ConnectTimeout=2 $host "docker ps --format '{{.Names}}'" 2>/dev/null)
  fi

  for c in $node_running; do
    running+="$c "
    node_map+="$c:$node "
  done
done

defined=$(yq e '.services | keys | .[]' $CLUSTER)

# =========================
# SERVICE RECONCILIATION
# =========================
for svc in $defined; do
  enabled=$(yq e ".services.$svc.enabled" $CLUSTER)
  stack=$(yq e ".services.$svc.stack" $CLUSTER)
  replicas=$(yq e ".services.$svc.replicas" $CLUSTER)

  [ "$replicas" = "null" ] && replicas=1

  # Match containers like: sonarr, sonarr-1, sonarr-2
  containers=$(echo "$running" | tr ' ' '\n' | grep "^$svc")
  count=$(echo "$containers" | grep -c "^$svc")

  # =========================
  # DISABLED SERVICE
  # =========================
  if [ "$enabled" != "true" ]; then
    if [ "$count" -gt 0 ]; then
      echo "[DISABLE] $svc shutting down" | tee -a $LOG

      for node in $nodes; do
        host=$(yq e ".nodes.$node.host" $CLUSTER)

        if [ "$host" = "localhost" ]; then
          docker compose -f docker/$stack/docker-compose.yml down
        else
          ssh $host "docker compose -f docker/$stack/docker-compose.yml down" 2>/dev/null
        fi
      done
    fi
    continue
  fi

  # =========================
  # SCHEDULER (placement)
  # =========================
  best_node=$(bash control-plane/agents/scheduler.sh $svc)
  best_host=$(yq e ".nodes.$best_node.host" $CLUSTER)

  echo "[ENSURE] $svc replicas=$replicas node=$best_node" | tee -a $LOG

  # =========================
  # APPLY STATE (IDEMPOTENT)
  # =========================
  if [ "$best_host" = "localhost" ]; then
    docker compose -f docker/$stack/docker-compose.yml up -d --scale $svc=$replicas
  else
    ssh $best_host "docker compose -f docker/$stack/docker-compose.yml up -d --scale $svc=$replicas" 2>/dev/null
  fi

  # =========================
  # HEALTH CHECK + SELF HEAL
  # =========================
  for c in $containers; do
    target_node=$(echo "$node_map" | tr ' ' '\n' | grep "^$c:" | cut -d':' -f2)
    target_host=$(yq e ".nodes.$target_node.host" $CLUSTER)

    if [ "$target_host" = "localhost" ]; then
      status=$(docker inspect --format='{{.State.Health.Status}}' $c 2>/dev/null)
      if [ "$status" = "unhealthy" ]; then
        echo "[HEAL] $c restarting" | tee -a $LOG
        docker restart $c
      fi
    else
      status=$(ssh $target_host "docker inspect --format='{{.State.Health.Status}}' $c" 2>/dev/null)
      if [ "$status" = "unhealthy" ]; then
        echo "[HEAL] $c restarting on $target_node" | tee -a $LOG
        ssh $target_host "docker restart $c" 2>/dev/null
      fi
    fi
  done
done

# =========================
# DRIFT DETECTION (FIXED)
# =========================
for c in $running; do
  base=$(echo $c | sed 's/-[0-9]\+$//')

  if ! echo "$defined" | grep -q "^$base$"; then
    echo "[DRIFT] Unknown container: $c" | tee -a $LOG
  fi
done

# =========================
# SUMMARY
# =========================
def_count=$(echo "$defined" | wc -w)
run_count=$(echo "$running" | wc -w)

echo "[SUMMARY] services=$def_count running=$run_count" >> $LOG
echo "[RECONCILE DONE]" >> $LOG