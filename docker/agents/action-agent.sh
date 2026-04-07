#!/bin/bash

STATE="/docker/state"
ACTIONS="$STATE/actions.txt"
LOG="/docker/logs/actions.log"

source /docker/connections.env 2>/dev/null
API="https://api.telegram.org/bot$BOT_TOKEN"

COOLDOWN="$STATE/cooldowns/action"

NOW=$(date +%s)
LAST=0
[ -f "$COOLDOWN" ] && LAST=$(cat $COOLDOWN)

# Skip if cooldown active (unless forced via Telegram approval)
if [ "$1" != "force" ] && [ $((NOW - LAST)) -lt 120 ]; then
  exit 0
fi

echo $NOW > $COOLDOWN

while read line; do
  NAME=$(echo $line | awk '{print $1}')
  ACTION=$(echo $line | awk '{print $2}')

  if [ "$ACTION" == "RESTART" ]; then
    docker restart $NAME
    echo "$(date) Restarted $NAME" >> $LOG

    # Notify via Telegram
    if [ -n "$BOT_TOKEN" ] && [ -n "$CHAT_ID" ]; then
      curl -s -X POST "$API/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="🛠 Restarted $NAME (auto)" > /dev/null
    fi
  fi

  if [ "$ACTION" == "ALERT" ]; then
    echo "$(date) ALERT: $NAME needs attention" >> $LOG

    # Send Telegram alert with approval request
    if [ -n "$BOT_TOKEN" ] && [ -n "$CHAT_ID" ]; then
      curl -s -X POST "$API/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="⚠️ $NAME issue detected

Action: $ACTION
Approve restart? (yes/no)" > /dev/null
    fi
  fi

  if [ "$ACTION" == "RESTART_SUGGESTED" ]; then
    echo "$(date) AI SUGGESTED restart: $NAME" >> $LOG

    if [ -n "$BOT_TOKEN" ] && [ -n "$CHAT_ID" ]; then
      curl -s -X POST "$API/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="🤖 AI recommends restarting $NAME

Approve? (yes/no)" > /dev/null
    fi
  fi

done < $ACTIONS
