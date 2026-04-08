#!/bin/bash

# REGISTRY AGENT - Tracks system state + services
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$BASE_DIR/control-plane/state/logs/registry.log"
CLUSTER="$BASE_DIR/control-plane/config/cluster.yml"
OUT="$BASE_DIR/control-plane/state/traefik-dynamic.yml"

echo "[REGISTRY] $(date)" >> "$LOG"

echo "http:" > "$OUT.tmp"
echo "  services:" >> "$OUT.tmp"

services=$(yq e '.services | keys | .[]' "$CLUSTER")
nodes=$(yq e '.nodes | keys | .[]' "$CLUSTER")

for svc in $services; do
  # Skip non-routable or missing port services
  port=$(yq e ".services.$svc.port" "$CLUSTER")
  if [ "$port" = "null" ] || [ -z "$port" ]; then continue; fi

  echo "    $svc:" >> "$OUT.tmp"
  echo "      loadBalancer:" >> "$OUT.tmp"
  echo "        servers:" >> "$OUT.tmp"

  found_any=false
  for node in $nodes; do
    host=$(yq e ".nodes.$node.host" "$CLUSTER")
    
    # Check if container is running on this specific host
    if [ "$host" = "localhost" ]; then
      running_local=$(docker ps --format '{{.Names}}' | grep "^$svc")
    else
      running_local=$(ssh -o ConnectTimeout=2 "$host" "docker ps --format '{{.Names}}'" 2>/dev/null | grep "^$svc")
    fi

    if [ -n "$running_local" ]; then
      for c in $running_local; do
        target=$(echo "$host" | cut -d'@' -f2 | cut -d':' -f1)
        [ "$target" = "localhost" ] && target="127.0.0.1"
        
        echo "          - url: \"http://$target:$port\"" >> "$OUT.tmp"
        found_any=true
      done
    fi
  done

  if [ "$found_any" = "true" ]; then
    echo "        healthCheck:" >> "$OUT.tmp"
    echo "          interval: 10s" >> "$OUT.tmp"
    echo "          timeout: 5s" >> "$OUT.tmp"
    echo "          path: /" >> "$OUT.tmp" 
  fi
done

echo "  routers:" >> "$OUT.tmp"
for svc in $services; do
  port=$(yq e ".services.$svc.port" "$CLUSTER")
  if [ "$port" = "null" ] || [ -z "$port" ]; then continue; fi
  
  echo "    $svc:" >> "$OUT.tmp"
  echo "      rule: \"Host(\`$svc.local\`)\"" >> "$OUT.tmp"
  echo "      service: $svc" >> "$OUT.tmp"
  echo "      entryPoints:" >> "$OUT.tmp"
  echo "        - web" >> "$OUT.tmp"
done

mv "$OUT.tmp" "$OUT"
echo "[REGISTRY] Updated cluster routing map" >> "$LOG"
