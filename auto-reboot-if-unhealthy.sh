#!/bin/bash

# Auto reboot if system unhealthy (high CPU or memory)

source .env

CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2 + $4}')
MEM=$(free | awk '/Mem:/ {printf("%.0f", $3/$2 * 100)}')

if [ "$MEM" -gt 95 ]; then
  curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
    -d chat_id="$CHAT_ID" \
    -d text="System unhealthy (memory high), rebooting"

  ./graceful-reboot.sh
fi
