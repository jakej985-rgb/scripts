#!/bin/bash

source "$(dirname "$0")/lib/env.sh"
LOG_DIR="/docker/maintenance/logs"
SUMMARY=""

for file in $LOG_DIR/*.log; do
  COUNT=$(grep -Ei "error|failed|timeout|unhealthy" "$file" | wc -l)
  if [ "$COUNT" -gt 0 ]; then
    SUMMARY+="$(basename $file): $COUNT issues\n"
  fi
done

[ ! -z "$SUMMARY" ] && curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
  -d chat_id="$CHAT_ID" \
  -d text="System Summary:\n$SUMMARY"
