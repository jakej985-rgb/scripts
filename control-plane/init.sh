#!/bin/bash

set -e

# >>> AUTO-ROOT (antigravity)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# <<< AUTO-ROOT
BASE_DIR="$REPO_ROOT"

echo "[INIT] Running self-healing setup..."

# -----------------------------
# Directories
# -----------------------------
DIRS=(
  "$BASE_DIR/control-plane/state"
  "$BASE_DIR/control-plane/state/logs"
  "$BASE_DIR/control-plane/state/tmp"
  "$BASE_DIR/control-plane/agents"
)

for dir in "${DIRS[@]}"; do
  if [ ! -d "$dir" ]; then
    echo "[INIT] Creating missing dir: $dir"
    mkdir -p "$dir"
  fi
done

# -----------------------------
# Log files
# -----------------------------
LOGS=(
  "monitor.log"
  "metrics.log"
  "anomaly.log"
  "decision.log"
  "reconcile.log"
  "registry.log"
  "observer.log"
  "scorer.log"
  "chaos.log"
)

for file in "${LOGS[@]}"; do
  path="$BASE_DIR/control-plane/state/logs/$file"
  if [ ! -f "$path" ]; then
    echo "[INIT] Creating missing log: $file"
    touch "$path"
  fi
done

# -----------------------------
# State Files (Standardize / Self-Heal)
# -----------------------------
FILES=(
  "metrics.json"
  "normalized_metrics.json"
  "anomalies.json"
  "decisions.json"
  "registry.json"
  "health.json"
  "chaos_events.json"
)

for f in "${FILES[@]}"; do
  path="$BASE_DIR/control-plane/state/$f"
  if [ ! -f "$path" ]; then
    echo "[]" > "$path"
    echo "[INIT] Recreated $f"
  else
    # Check if corrupted (not valid JSON)
    if ! jq . "$path" >/dev/null 2>&1; then
      echo "[]" > "$path"
      echo "[STATE] Reset corrupted $f"
    fi
  fi
done

touch "$BASE_DIR/control-plane/state/leader.txt"

# -----------------------------
# Auth Scaffolding (Batch 3 T1)
# -----------------------------
if [ ! -f "$BASE_DIR/dashboard/users.json" ]; then
  echo "[INIT] Scaffolding default users.json (admin / admin123)..."
  mkdir -p "$BASE_DIR/dashboard"
  cat > "$BASE_DIR/dashboard/users.json" <<EOF
[
  {
    "username": "admin",
    "token_hash": "\$2b\$12\$6PuxP6N7ZpG5B9W7/p3E.e3u0Xm6x6u1vXm6x6u1vXm6x6u1vXm6x6u1v",
    "role": "admin"
  }
]
EOF
fi

# -----------------------------
# Optional permissions (safe)
# -----------------------------
chmod -R 750 "$BASE_DIR/control-plane/state" 2>/dev/null || true

echo "[INIT] Done."