#!/bin/bash

BOT_TOKEN="YOUR_BOT_TOKEN"
ALLOWED_CHAT_ID="YOUR_CHAT_ID"
LAST_UPDATE_FILE="/tmp/telegram_last_update"

LAST_UPDATE=$(cat $LAST_UPDATE_FILE 2>/dev/null || echo 0)
UPDATES=$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getUpdates?offset=$LAST_UPDATE")

echo "$UPDATES" | jq -c '.result[]' | while read update; do

  UPDATE_ID=$(echo $update | jq '.update_id')
  CHAT_ID=$(echo $update | jq '.message.chat.id')
  MESSAGE=$(echo $update | jq -r '.message.text')

  echo $((UPDATE_ID+1)) > $LAST_UPDATE_FILE

  # 🔐 Ignore unauthorized users
  if [ "$CHAT_ID" != "$ALLOWED_CHAT_ID" ]; then
    continue
  fi

  case "$MESSAGE" in

    "/status")
      docker ps --format "table {{.Names}}\t{{.Status}}" > /tmp/status.txt
      curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendDocument" \
        -F chat_id=$ALLOWED_CHAT_ID \
        -F document=@/tmp/status.txt
      ;;

    "/restart "*)
      NAME=$(echo $MESSAGE | cut -d' ' -f2)
      docker restart $NAME
      ;;

    "/logs "*)
      NAME=$(echo $MESSAGE | cut -d' ' -f2)
      docker logs --tail 100 $NAME > /tmp/logs.txt
      curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendDocument" \
        -F chat_id=$ALLOWED_CHAT_ID \
        -F document=@/tmp/logs.txt
      ;;

  esac

done
