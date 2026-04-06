#!/bin/bash

source /docker/scripts/docker-maintenance/notify.sh

LOG_DIR="/docker/maintenance/logs"

SUMMARY=""

for file in $LOG_DIR/*.log; do
  ERRORS=$(grep -Ei "error|failed|timeout|unhealthy" "$file" | wc -l)

  if [ "$ERRORS" -gt 0 ]; then
    SUMMARY+="$(basename $file): $ERRORS issues\n"
  fi
done

if [ ! -z "$SUMMARY" ]; then
  send_telegram "🧠 System Summary:\n$SUMMARY"
fi
