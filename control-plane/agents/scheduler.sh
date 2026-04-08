#!/bin/bash
# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT

# scheduler.sh - Decides node placement based on least-loaded strategy

CLUSTER="$REPO_ROOT/control-plane/config/cluster.yml"
METRICS="$REPO_ROOT/control-plane/state/metrics.json"

svc=$1
nodes=$(yq e '.nodes | keys | .[]' $CLUSTER)

best_node=""
lowest_cpu=999

for node in $nodes; do
  cpu=$(jq -r ".$node.cpu" $METRICS 2>/dev/null)
  
  # Default to 0 if metrics are missing
  if [ "$cpu" = "null" ] || [ -z "$cpu" ]; then cpu=0; fi

  if (( $(echo "$cpu < $lowest_cpu" | bc -l) )); then
    lowest_cpu=$cpu
    best_node=$node
  fi
done

echo $best_node
