#!/bin/bash
# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT

# registry.sh - Generates Traefik dynamic configuration for cluster-wide routing

CLUSTER="$REPO_ROOT/control-plane/config/cluster.yml"
OUT="$REPO_ROOT/control-plane/state/traefik-dynamic.yml"
LOG="$REPO_ROOT/control-plane/state/logs/reconcile.log"

echo "http:" > $OUT
echo "  services:" >> $OUT

services=$(yq e '.services | keys | .[]' $CLUSTER)
nodes=$(yq e '.nodes | keys | .[]' $CLUSTER)

for svc in $services; do
  # Skip non-routable or missing port services
  port=$(yq e ".services.$svc.port" $CLUSTER)
  if [ "$port" = "null" ] || [ -z "$port" ]; then continue; fi

  echo "    $svc:" >> $OUT
  echo "      loadBalancer:" >> $OUT
  echo "        servers:" >> $OUT

  found_any=false
  for node in $nodes; do
    host=$(yq e ".nodes.$node.host" $CLUSTER)
    
    # Check if container is running on this specific host
    if [ "$host" = "localhost" ]; then
      running_local=$(docker ps --format '{{.Names}}' | grep "^$svc")
    else
      running_local=$(ssh -o ConnectTimeout=2 $host "docker ps --format '{{.Names}}'" 2>/dev/null | grep "^$svc")
    fi

    if [ -n "$running_local" ]; then
      for c in $running_local; do
        # Use actual node host for routing
        target=$(echo $host | cut -d'@' -f2)
        if [ "$target" = "localhost" ]; then target="127.0.0.1"; fi
        
        echo "          - url: \"http://$target:$port\"" >> $OUT
        found_any=true
      done
    fi
  done

  # Add Health check logic if containers found
  if [ "$found_any" = "true" ]; then
    echo "        healthCheck:" >> $OUT
    echo "          interval: 10s" >> $OUT
    echo "          timeout: 5s" >> $OUT
    # Use generic status path or service specific if needed
    echo "          path: /" >> $OUT 
  fi
done

echo "  routers:" >> $OUT
for svc in $services; do
  port=$(yq e ".services.$svc.port" $CLUSTER)
  if [ "$port" = "null" ] || [ -z "$port" ]; then continue; fi
  
  echo "    $svc:" >> $OUT
  echo "      rule: \"Host(\`$svc.local\`)\"" >> $OUT
  echo "      service: $svc" >> $OUT
  echo "      entryPoints:" >> $OUT
  echo "        - web" >> $OUT
done

echo "[REGISTRY] Updated cluster routing map" >> $LOG
