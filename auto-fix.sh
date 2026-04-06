#!/bin/bash

# 🔧 Targeted auto-fix system

source "$(dirname "$0")/lib/env.sh"

HOST=$(hostname)

send() {
  curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
    -d chat_id="$CHAT_ID" \
    -d text="$1" > /dev/null
}

# Detect highest CPU container
TOP_CONTAINER=$(docker stats --no-stream --format "{{.Name}} {{.CPUPerc}}" | sort -k2 -hr | head -n1 | awk '{print $1}')

# Restart if CPU spike
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2+$4}')

if [ "$ENABLE_AUTO_FIX" = "true" ]; then
  if (( $(echo "$CPU > ${CPU_THRESHOLD:-90}" | bc -l) )); then
    send "🔧 High CPU detected ($CPU%). Restarting $TOP_CONTAINER"
    docker restart "$TOP_CONTAINER"
  fi

  # Memory pressure
  MEM=$(free | awk '/Mem:/ {printf("%.0f", $3/$2 * 100)}')

  if [ "$MEM" -gt "${MEM_THRESHOLD:-90}" ]; then
    send "🔧 High memory usage ($MEM%). Restarting top container"
    docker restart "$TOP_CONTAINER"
  fi
fi
