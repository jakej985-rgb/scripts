#!/bin/bash

# >>> AUTO-ROOT (antigravity)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# <<< AUTO-ROOT

STACK=$1

echo "[EXEC] $STACK"
docker compose -f "$REPO_ROOT/docker/$STACK/docker-compose.yml" up -d
