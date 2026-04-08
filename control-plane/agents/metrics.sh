#!/bin/bash
# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT

# metrics.sh - Collects cluster-wide node metrics

CLUSTER="$REPO_ROOT/control-plane/config/cluster.yml"
METRICS="$REPO_ROOT/control-plane/state/metrics.json"

echo "{" > $METRICS

nodes=$(yq e '.nodes | keys | .[]' $CLUSTER)
count=$(echo "$nodes" | wc -w)
i=0

for node in $nodes; do
  host=$(yq e ".nodes.$node.host" $CLUSTER)
  
  if [ "$host" = "localhost" ]; then
    # Local CPU usage (fallback for single-node development)
    cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print 100 - $8}')
  else
    # Remote CPU usage via SSH
    cpu=$(ssh -o ConnectTimeout=2 $host "top -bn1 | grep 'Cpu(s)' | awk '{print 100 - \$8}'" 2>/dev/null)
  fi

  # Fallback if metrics fail
  if [ -z "$cpu" ]; then cpu=0; fi

  i=$((i+1))
  comma=","
  if [ $i -eq $count ]; then comma=""; fi

  echo "  \"$node\": { \"cpu\": $cpu }$comma" >> $METRICS
done

echo "}" >> $METRICS
