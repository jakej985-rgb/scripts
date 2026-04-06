#!/bin/bash

source connections.env
LOG_DIR="/docker/maintenance/logs"
KEYWORDS="error|failed|unhealthy|panic|critical"

for file in $LOG_DIR/*.log; do
  MSG=$(grep -Ei "$KEYWORDS" "$file" | tail -n 10)
  if [ ! -z "$MSG" ]; then
    curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
      -d chat_id="$CHAT_ID" \
      -d text="$(basename $file):\n$MSG"
  fi
done
