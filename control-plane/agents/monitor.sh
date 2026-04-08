#!/bin/bash

# MONITOR AGENT - Gathers raw system + container data
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$BASE_DIR/control-plane/state/logs/monitor.log"
OUT="$BASE_DIR/control-plane/state/metrics.json"

echo "[MONITOR] $(date)" >> "$LOG"

# Write to temp and move for atomic update
docker ps -a --format '{{json .}}' > "${OUT}.tmp"
mv "${OUT}.tmp" "$OUT"
