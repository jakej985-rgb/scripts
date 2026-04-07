#!/bin/bash

# 📲 Telegram Agent v2.2 — Approval + Control
# Polls for commands, handles yes/no approval flow
# Runs as a long-lived daemon (via Docker or systemd)

source /docker/connections.env 2>/dev/null

STATE="/docker/state"
API="https://api.telegram.org/bot$BOT_TOKEN"

LAST_UPDATE_FILE="$STATE/telegram_offset"

OFFSET=0
[ -f "$LAST_UPDATE_FILE" ] && OFFSET=$(cat $LAST_UPDATE_FILE)

UPDATES=$(curl -s "$API/getUpdates?offset=$OFFSET")

echo "$UPDATES" | jq -c '.result[]' 2>/dev/null | while read update; do
  ID=$(echo $update | jq '.update_id')
  TEXT=$(echo $update | jq -r '.message.text')
  CHAT=$(echo $update | jq -r '.message.chat.id')

  echo $((ID+1)) > $LAST_UPDATE_FILE

  # Security: only accept from authorized chat
  if [ "$CHAT" != "$CHAT_ID" ]; then
    continue
  fi

  case "$TEXT" in

    "yes")
      # Check for pending actions
      if [ -f "$STATE/actions.txt" ]; then
        bash /docker/agents/action-agent.sh force
        curl -s -X POST "$API/sendMessage" \
          -d chat_id="$CHAT_ID" \
          -d text="✅ Approved. Actions executed." > /dev/null
      else
        curl -s -X POST "$API/sendMessage" \
          -d chat_id="$CHAT_ID" \
          -d text="ℹ️ No pending actions." > /dev/null
      fi
      ;;

    "no")
      > "$STATE/actions.txt"
      curl -s -X POST "$API/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="❌ Actions rejected. Queue cleared." > /dev/null
      ;;

    "status")
      PS=$(docker ps --format "{{.Names}}  {{.Status}}" 2>/dev/null)
      curl -s -X POST "$API/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="📦 Containers:
$PS" > /dev/null
      ;;

    "/restart "*)
      NAME=$(echo "$TEXT" | awk '{print $2}')
      if docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
        docker restart "$NAME"
        curl -s -X POST "$API/sendMessage" \
          -d chat_id="$CHAT_ID" \
          -d text="🔄 Restarted: $NAME" > /dev/null
        echo "$(date) Manual restart: $NAME (Telegram)" >> /docker/logs/actions.log
      else
        curl -s -X POST "$API/sendMessage" \
          -d chat_id="$CHAT_ID" \
          -d text="❌ Container not found: $NAME" > /dev/null
      fi
      ;;

    "/logs "*)
      NAME=$(echo "$TEXT" | awk '{print $2}')
      if docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
        TAIL=$(docker logs --tail 30 "$NAME" 2>&1)
        curl -s -X POST "$API/sendMessage" \
          -d chat_id="$CHAT_ID" \
          -d text="📜 $NAME logs:
$TAIL" > /dev/null
      else
        curl -s -X POST "$API/sendMessage" \
          -d chat_id="$CHAT_ID" \
          -d text="❌ Container not found: $NAME" > /dev/null
      fi
      ;;

    "/help")
      curl -s -X POST "$API/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="🤖 M3TAL Commands:
status — container overview
yes — approve pending action
no — reject pending action
/restart [name] — restart container
/logs [name] — tail 30 log lines
/help — this message" > /dev/null
      ;;

  esac
done
