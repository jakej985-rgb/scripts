#!/bin/bash

STATE="control-plane/state"
ACTIONS="$STATE/decisions.json"
LOG="control-plane/state/logs/actions.log"

source control-plane/config/connections.env 2>/dev/null
API="https://api.telegram.org/bot$BOT_TOKEN"

COOLDOWN="$STATE/cooldowns/action"

NOW=$(date +%s)
LAST=0
[ -f "$COOLDOWN" ] && LAST=$(cat $COOLDOWN)

# Skip if cooldown active (unless forced via Telegram/Dashboard approval)
if [ "$1" != "force" ] && [ $((NOW - LAST)) -lt 120 ]; then
  exit 0
fi

echo $NOW > $COOLDOWN

send() {
  if [ -n "$BOT_TOKEN" ] && [ -n "$CHAT_ID" ]; then
    curl -s -X POST "$API/sendMessage" \
      -d chat_id="$CHAT_ID" \
      -d text="$1" > /dev/null
  fi
}

while read line; do
  NAME=$(echo $line | awk '{print $1}')
  ACTION=$(echo $line | awk '{print $2}')
  DETAIL=$(echo $line | awk '{$1=$2=""; print $0}' | sed 's/^ *//')

  case "$ACTION" in
    "RESTART")
      bash scripts/docker-exec.sh restart $NAME
      echo "{\"time\":\"$(date -Iseconds)\",\"event\":\"restart\",\"container\":\"$NAME\",\"type\":\"auto\"}" >> $LOG
      send "🛠 Restarted $NAME (auto)"
      ;;

    "ALERT")
      echo "{\"time\":\"$(date -Iseconds)\",\"event\":\"alert\",\"container\":\"$NAME\",\"reason\":\"needs attention\"}" >> $LOG
      send "⚠️ $NAME issue detected
Action: $ACTION
Approve restart? (yes/no)"
      ;;

    "RESTART_SUGGESTED")
      echo "{\"time\":\"$(date -Iseconds)\",\"event\":\"ai_suggestion\",\"container\":\"$NAME\",\"reason\":\"restart\"}" >> $LOG
      send "🤖 AI recommends restarting $NAME
Approve? (yes/no)"
      ;;

    "ALERT_CPU")
      echo "{\"time\":\"$(date -Iseconds)\",\"event\":\"cpu_alert\",\"container\":\"$NAME\",\"detail\":\"$DETAIL\"}" >> $LOG
      send "🔥 $NAME — HIGH CPU ($DETAIL)"
      ;;

    "ALERT_MEM")
      echo "{\"time\":\"$(date -Iseconds)\",\"event\":\"mem_alert\",\"container\":\"$NAME\",\"detail\":\"$DETAIL\"}" >> $LOG
      send "🔥 $NAME — HIGH MEMORY ($DETAIL)"
      ;;

    ALERT_DEP_*)
      echo "{\"time\":\"$(date -Iseconds)\",\"event\":\"dependency_alert\",\"container\":\"$NAME\",\"dependency\":\"$DETAIL\"}" >> $LOG
      send "🔗 $NAME degraded — dependency $DETAIL is down"
      ;;
  esac

done < $ACTIONS
