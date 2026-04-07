#!/bin/bash

# ⏰ Scheduler Agent v5.2 — Cluster-Wide Job Execution
# Reads jobs.json and executes matching jobs based on cron-like schedule
# Designed to run every minute from m3tal.sh

JOBS="/docker/config/jobs.json"
STATE="/docker/state"
LOG="/docker/logs/scheduler.log"

if [ ! -f "$JOBS" ]; then exit 0; fi


CURRENT_MIN=$(date +%M)
CURRENT_HOUR=$(date +%H)
CURRENT_DOM=$(date +%d)
CURRENT_MON=$(date +%m)
CURRENT_DOW=$(date +%u)

# Simple cron field match (supports * and specific values)
match_field() {
  local field="$1" value="$2"
  if [ "$field" == "*" ]; then return 0; fi
  # Handle */N interval syntax
  if [[ "$field" == "*/"* ]]; then
    local interval="${field#*/}"
    if [ $((value % interval)) -eq 0 ]; then return 0; fi
    return 1
  fi
  if [ "$field" == "$value" ]; then return 0; fi
  return 1
}

jq -c '.[]' "$JOBS" 2>/dev/null | while read job; do
  NAME=$(echo "$job" | jq -r '.name')
  CMD=$(echo "$job" | jq -r '.command')
  SCHEDULE=$(echo "$job" | jq -r '.schedule')
  NODE_TARGET=$(echo "$job" | jq -r '.node // "local"')

  # Parse cron fields
  CRON_MIN=$(echo "$SCHEDULE" | awk '{print $1}')
  CRON_HOUR=$(echo "$SCHEDULE" | awk '{print $2}')
  CRON_DOM=$(echo "$SCHEDULE" | awk '{print $3}')
  CRON_MON=$(echo "$SCHEDULE" | awk '{print $4}')
  CRON_DOW=$(echo "$SCHEDULE" | awk '{print $5}')

  # Check if current time matches schedule
  if match_field "$CRON_MIN" "$CURRENT_MIN" && \
     match_field "$CRON_HOUR" "$CURRENT_HOUR" && \
     match_field "$CRON_DOM" "$CURRENT_DOM" && \
     match_field "$CRON_MON" "$CURRENT_MON" && \
     match_field "$CRON_DOW" "$CURRENT_DOW"; then

    # Cooldown check (prevent double execution within same minute)
    COOLDOWN_FILE="$STATE/cooldowns/job_${NAME}"
    if [ -f "$COOLDOWN_FILE" ] && [ $(($(date +%s) - $(cat "$COOLDOWN_FILE"))) -lt 60 ]; then
      continue
    fi
    date +%s > "$COOLDOWN_FILE"

    if [ "$NODE_TARGET" == "local" ] || [ "$NODE_TARGET" == "$(hostname)" ]; then
      echo "$(date) JOB: $NAME executing locally" >> "$LOG"
      bash -c "$CMD" >> "$LOG" 2>&1
    elif [ "$NODE_TARGET" == "all" ]; then
      echo "$(date) JOB: $NAME dispatching to cluster" >> "$LOG"
      source /docker/connections.env 2>/dev/null
      MASTER="${MASTER_URL:-http://localhost:8888}"
      curl -s --max-time 5 -X POST "$MASTER/api/run_job/$NAME" > /dev/null 2>&1 || true
    fi
  fi
done
