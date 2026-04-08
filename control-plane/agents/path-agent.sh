#!/bin/bash

# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT

# PATH AGENT
# Enforces safe, portable paths across M3tal-Media-Server
# Self-Heals required files and directories

STATE_DIR="$REPO_ROOT/control-plane/state"
LOG_DIR="$REPO_ROOT/control-plane/logs"
LEADER_FILE="$STATE_DIR/leader.txt"

# Ensure directories exist
mkdir -p "$STATE_DIR"
mkdir -p "$LOG_DIR"

# Ensure leader.txt exists
if [ ! -f "$LEADER_FILE" ]; then
  echo "none" > "$LEADER_FILE"
fi

exit 0
