#!/bin/bash

# 🔍 Post-reboot verification + alert

source .env

HOST=$(hostname)

sleep 30

STATUS=$(docker ps --format "{{.Names}}: {{.Status}}")

curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
  -d chat_id="$CHAT_ID" \
  -d text="✅ [$HOST] Server is back online\n\nContainers:\n$STATUS" > /dev/null
