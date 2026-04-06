#!/bin/bash

source /docker/scripts/docker-maintenance/notify.sh

LOG_DIR="/docker/maintenance/logs"
KEYWORDS="error|failed|unhealthy|panic|critical"

for file in $LOG_DIR/*.log; do
  MSG=$(grep -Ei "$KEYWORDS" "$file" | tail -n 20)

  if [ ! -z "$MSG" ]; then
    send_telegram "🚨 Issue in $(basename $file):\n$MSG"
  fi
done
