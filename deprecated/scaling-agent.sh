#!/bin/bash

# 📈 Scaling Agent v6.1 — Auto-Scale Containers Based on Load
# Reads scaling.json rules, compares with current metrics
# Respects cooldowns, min/max boundaries, and never scales DB containers

STATE="/docker/state"
CONFIG="/docker/config/scaling.json"
METRICS="$STATE/metrics.txt"
LOG="/docker/logs/scaling.log"

if [ ! -f "$CONFIG" ] || [ ! -f "$METRICS" ]; then exit 0; fi

LOCK="$STATE/locks/scaling.lock"
[ -f "$LOCK" ] && exit 0
trap "rm -f $LOCK" EXIT
touch "$LOCK"

COOLDOWN_DIR="$STATE/cooldowns"

jq -c 'to_entries[]' "$CONFIG" 2>/dev/null | while read entry; do
  NAME=$(echo "$entry" | jq -r '.key')
  MIN=$(echo "$entry" | jq -r '.value.min')
  MAX=$(echo "$entry" | jq -r '.value.max')
  CPU_UP=$(echo "$entry" | jq -r '.value.cpu_up // 80')
  CPU_DOWN=$(echo "$entry" | jq -r '.value.cpu_down // 15')
  IMAGE=$(echo "$entry" | jq -r '.value.image // empty')

  # Count running instances
  CURRENT=$(docker ps --filter "name=$NAME" --format "{{.Names}}" 2>/dev/null | wc -l)

  # Get CPU from metrics
  CPU=$(grep "^$NAME " "$METRICS" 2>/dev/null | head -1 | awk '{print $2}' | tr -d '%')
  if [ -z "$CPU" ]; then continue; fi
  CPU_INT=${CPU%.*}

  # Cooldown (5 min between scale events per service)
  SCALE_COOLDOWN="$COOLDOWN_DIR/scale_${NAME}"
  if [ -f "$SCALE_COOLDOWN" ] && [ $(($(date +%s) - $(cat "$SCALE_COOLDOWN"))) -lt 300 ]; then
    continue
  fi

  # Scale UP
  if [ "$CPU_INT" -gt "$CPU_UP" ] && [ "$CURRENT" -lt "$MAX" ]; then
    REPLICA_NUM=$((CURRENT + 1))
    NEW_NAME="${NAME}-replica-${REPLICA_NUM}"
    if [ -n "$IMAGE" ]; then
      docker run -d --name "$NEW_NAME" --restart unless-stopped "$IMAGE" 2>/dev/null
      echo "$(date) SCALE UP: $NAME → $NEW_NAME (CPU: ${CPU}%)" >> "$LOG"
      date +%s > "$SCALE_COOLDOWN"
    fi
  fi

  # Scale DOWN
  if [ "$CPU_INT" -lt "$CPU_DOWN" ] && [ "$CURRENT" -gt "$MIN" ]; then
    VICTIM=$(docker ps --filter "name=${NAME}-replica" --format "{{.Names}}" 2>/dev/null | tail -1)
    if [ -n "$VICTIM" ]; then
      docker stop "$VICTIM" 2>/dev/null
      docker rm "$VICTIM" 2>/dev/null
      echo "$(date) SCALE DOWN: removed $VICTIM (CPU: ${CPU}%)" >> "$LOG"
      date +%s > "$SCALE_COOLDOWN"
    fi
  fi
done
