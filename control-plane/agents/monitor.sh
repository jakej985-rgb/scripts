#!/bin/bash
# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT

# MONITOR AGENT
# Gathers all container states (including exited) and writes to state.json
docker ps -a --format '{{json .}}' > "$REPO_ROOT/control-plane/state/state.json"
