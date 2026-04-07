#!/bin/bash

CLUSTER_FILE="control-plane/config/cluster.yml"

echo "[RECONCILE] Starting..."

# get running containers
running=$(docker ps --format "{{.Names}}")

# parse services
services=$(yq e '.services | keys | .[]' $CLUSTER_FILE)

for svc in $services; do
  enabled=$(yq e ".services.$svc.enabled" $CLUSTER_FILE)
  stack=$(yq e ".services.$svc.stack" $CLUSTER_FILE)

  if [ "$enabled" = "true" ]; then
    if ! echo "$running" | grep -q "$svc"; then
      echo "[FIX] $svc missing → starting stack $stack"
      bash scripts/docker-exec.sh $stack
    fi
  else
    if echo "$running" | grep -q "$svc"; then
      echo "[FIX] $svc disabled → stopping"
      bash scripts/docker-exec.sh stop $svc
    fi
  fi
done

echo "[RECONCILE] Done"
