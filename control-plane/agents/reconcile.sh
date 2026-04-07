#!/bin/bash

LOG="control-plane/state/logs/reconcile.log"
STRICT=false
CLUSTER="control-plane/config/cluster.yml"

# =========================
# LOAD MULTI-NODE STATE
# =========================
nodes=$(yq e '.nodes | keys | .[]' $CLUSTER)
running=""
node_map=""

echo "[RECONCILE] $(date)" >> $LOG

for node in $nodes; do
  host=$(yq e ".nodes.$node.host" $CLUSTER)
  if [ "$host" = "localhost" ]; then
    node_running=$(docker ps --format "{{.Names}}")
  else
    # Check node health first
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

  containers=$(echo "$running" | tr ' ' '\n' | grep "^$svc")
  count=$(echo "$containers" | grep -c "^$svc")

  # CPU-based Auto Scale Decision
  if [ "$autoscale" = "true" ]; then
    # Parse metrics.json for aggregate/avg CPU or per-node logic? 
    # For now, keep it simple: use current avg across cluster or just the logic from spec
    cpu=$(jq -r ".[] .cpu" control-plane/state/metrics.json | awk '{ sum += $1; n++ } END { if (n > 0) print sum / n; else print 0 }')
    
    if [ -n "$cpu" ]; then
      if (( $(echo "$cpu > $cpu_threshold" | bc -l) )) && [ "$count" -lt "$max" ]; then
        echo "[AUTO-SCALE-UP] $svc cluster_cpu=$cpu%" | tee -a $LOG
        replicas=$(($count + 1))
      fi
      if (( $(echo "$cpu < 30" | bc -l) )) && [ "$count" -gt "$min" ]; then
        echo "[AUTO-SCALE-DOWN] $svc cluster_cpu=$cpu%" | tee -a $LOG
        replicas=$(($count - 1))
      fi
    fi
  fi

  # 1. Disabled handling FIRST
  if [ "$enabled" != "true" ]; then
    if [ "$count" -gt 0 ]; then
      for c in $containers; do
        target_node=$(echo "$node_map" | tr ' ' '\n' | grep "^$c:" | cut -d':' -f2)
        target_host=$(yq e ".nodes.$target_node.host" $CLUSTER)
        echo "[STOP] $c disabled on $target_node" | tee -a $LOG
        if [ "$target_host" = "localhost" ]; then
          docker stop $c
        else
          ssh $target_host "docker stop $c" 2>/dev/null
        fi
      done
    fi
    continue
  fi

  # 2. Existence check + Scaling
  if [ "$count" -lt "$replicas" ]; then
    missing=$(($replicas - $count))
    for i in $(seq 1 $missing); do
      # Ask scheduler WHERE to put it
      best_node=$(bash control-plane/agents/scheduler.sh $svc)
      best_host=$(yq e ".nodes.$best_node.host" $CLUSTER)
      
      name="$svc"
      if [ $replicas -gt 1 ] || [ $count -gt 0 ]; then
         # Generate unique name for replicas
         name="$svc-$(date +%s%N | cut -c1-12)"
      fi

      echo "[SCHEDULE] $svc -> $best_node ($name)" | tee -a $LOG
      if [ "$best_host" = "localhost" ]; then
        docker compose -f docker/$stack/docker-compose.yml run -d --name $name $svc
      else
        ssh $best_host "docker compose -f docker/$stack/docker-compose.yml run -d --name $name $svc" 2>/dev/null
      fi
    done
  fi

  if [ "$count" -gt "$replicas" ]; then
    echo "[SCALE-DOWN] $svc ($count -> $replicas)" | tee -a $LOG
    extras=$(echo "$containers" | tail -n +$(($replicas + 1)))
    for c in $extras; do
      target_node=$(echo "$node_map" | tr ' ' '\n' | grep "^$c:" | cut -d':' -f2)
      target_host=$(yq e ".nodes.$target_node.host" $CLUSTER)
      echo "[REMOVE] $c from $target_node" | tee -a $LOG
      if [ "$target_host" = "localhost" ]; then
        docker stop $c && docker rm $c
      else
        ssh $target_host "docker stop $c && docker rm $c" 2>/dev/null
      fi
    done
  fi

  # 3. Health checks
  for c in $containers; do
    target_node=$(echo "$node_map" | tr ' ' '\n' | grep "^$c:" | cut -d':' -f2)
    target_host=$(yq e ".nodes.$target_node.host" $CLUSTER)
    if [ "$target_host" = "localhost" ]; then
      status=$(docker inspect --format='{{.State.Health.Status}}' $c 2>/dev/null)
      if [ "$status" = "unhealthy" ]; then
        echo "[HEAL] $c unhealthy on $target_node" | tee -a $LOG
        docker restart $c
      fi
    else
      status=$(ssh $target_host "docker inspect --format='{{.State.Health.Status}}' $c" 2>/dev/null)
      if [ "$status" = "unhealthy" ]; then
        echo "[HEAL] $c unhealthy on $target_node" | tee -a $LOG
        ssh $target_host "docker restart $c" 2>/dev/null
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
  fi
done

# =========================
# SUMMARY
# =========================
def_count=$(echo "$defined" | wc -w)
run_count=$(echo "$running" | wc -w)
echo "[SUMMARY] services=$def_count running=$run_count" >> $LOG
echo "[RECONCILE DONE]" >> $LOG
