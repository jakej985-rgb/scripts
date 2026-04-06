#!/bin/bash

BOT_TOKEN="YOUR_BOT_TOKEN"
CHAT_ID="YOUR_CHAT_ID"

curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
  -d chat_id="$CHAT_ID" \
  -d text="Control Panel" \
  -d reply_markup='{"inline_keyboard":[[{"text":"Status","callback_data":"status"},{"text":"Restart Sonarr","callback_data":"restart_sonarr"}],[{"text":"Logs Jellyfin","callback_data":"logs_jellyfin"}]]}'
