#!/bin/bash

source connections.env
LAST_UPDATE_FILE="/tmp/telegram_last_update"
LAST_UPDATE=$(cat $LAST_UPDATE_FILE 2>/dev/null || echo 0)

UPDATES=$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getUpdates?offset=$LAST_UPDATE")

echo "$UPDATES" | jq -c '.result[]' | while read update; do
  UPDATE_ID=$(echo $update | jq '.update_id')
  CHAT=$(echo $update | jq '.message.chat.id')
  MSG=$(echo $update | jq -r '.message.text')

  echo $((UPDATE_ID+1)) > $LAST_UPDATE_FILE

  [ "$CHAT" != "$CHAT_ID" ] && continue

  case "$MSG" in
    "/status")
      docker ps --format "table {{.Names}}\t{{.Status}}" > /tmp/status.txt
      curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendDocument" \
        -F chat_id=$CHAT_ID -F document=@/tmp/status.txt
      ;;
    "/restart "*)
      NAME=$(echo $MSG | cut -d' ' -f2)
      docker restart $NAME
      ;;
    "/logs "*)
      NAME=$(echo $MSG | cut -d' ' -f2)
      docker logs --tail 100 $NAME > /tmp/logs.txt
      curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendDocument" \
        -F chat_id=$CHAT_ID -F document=@/tmp/logs.txt
      ;;
  esac
done
