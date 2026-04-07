#!/bin/bash

# ===== LOAD ENV =====
set -a
source /docker/maintenance/scripts/connections.env
set +a

API="https://api.telegram.org/bot$BOT_TOKEN"
LOG_FILE="/docker/maintenance/logs/auto-heal.log"

send_msg() {
    curl -s -X POST "$API/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="$1" >/dev/null
}

log() {
    echo "$(date '+%F %T') - $1" >> "$LOG_FILE"
}

for NAME in $(docker ps -a --format "{{.Names}}"); do

    STATUS=$(docker inspect --format='{{.State.Status}}' "$NAME")
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$NAME" 2>/dev/null)

    # ===== STOPPED =====
    if [ "$STATUS" != "running" ]; then
        docker start "$NAME"
        log "$NAME was stopped → started"
        send_msg "🛠 Started: $NAME"
        continue
    fi

    # ===== UNHEALTHY =====
    if [ "$HEALTH" == "unhealthy" ]; then
        docker restart "$NAME"
        log "$NAME unhealthy → restarted"
        send_msg "⚠ Restarted unhealthy: $NAME"
    fi

done
