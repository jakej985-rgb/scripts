#!/bin/bash

# 🔄 Safe system reboot with notification

source .env

HOST=$(hostname)
TIME=$(date)

# Notify before reboot
curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
  -d chat_id="$CHAT_ID" \
  -d text="⚠️ [$HOST] System reboot initiated at $TIME"

# Give time for message to send
sleep 5

# Reboot system
sudo reboot
