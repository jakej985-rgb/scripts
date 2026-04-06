#!/bin/bash

# 🧠 Graceful reboot: notify → stop containers → optional backup → reboot

source .env

HOST=$(hostname)
TIME=$(date)

send_msg() {
  curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
    -d chat_id="$CHAT_ID" \
    -d text="$1" > /dev/null
}

send_msg "⚠️ [$HOST] Graceful reboot starting at $TIME"

# Stop containers cleanly
send_msg "🛑 Stopping containers..."
docker ps -q | xargs -r docker stop

# Optional quick backup trigger (non-blocking)
if [ -x "./auto-backup.sh" ]; then
  send_msg "💾 Running quick backup before reboot..."
  ./auto-backup.sh &
fi

sleep 5

send_msg "🔁 Rebooting now"

sudo reboot
