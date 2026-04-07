#!/bin/bash

# ===== LOAD ENV =====
set -a
source /docker/maintenance/scripts/connections.env
set +a

API="https://api.telegram.org/bot$BOT_TOKEN"
LOG_FILE="/docker/maintenance/logs/telegram-control.log"
LAST_UPDATE_FILE="/tmp/telegram_last_update"

log() {
    echo "$(date '+%F %T') - $1" >> "$LOG_FILE"
}

send_msg() {
    curl -s -X POST "$API/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="$1" \
        -d parse_mode="Markdown" >/dev/null
}

# ===== INIT =====
LAST_UPDATE=$(cat "$LAST_UPDATE_FILE" 2>/dev/null || echo 0)

while true; do

    UPDATES=$(curl -s "$API/getUpdates?offset=$LAST_UPDATE")

    # FIX: prevent jq crash on empty
    echo "$UPDATES" | jq -c '.result[]?' 2>/dev/null | while read update; do

        UPDATE_ID=$(echo "$update" | jq '.update_id')
        CHAT=$(echo "$update" | jq '.message.chat.id')
        MSG=$(echo "$update" | jq -r '.message.text')

        echo $((UPDATE_ID+1)) > "$LAST_UPDATE_FILE"

        # ===== SECURITY =====
        if [ "$CHAT" != "$CHAT_ID" ]; then
            log "Blocked unauthorized chat: $CHAT"
            continue
        fi

        log "Command: $MSG"

        case "$MSG" in

            "/status")
                PS=$(docker ps --format "table {{.Names}}\t{{.Status}}")
                STATS=$(docker stats --no-stream \
                    --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" \
                    | sort -k2 -hr | column -t)

                send_msg "📦 *Docker Status:*
\`\`\`
$PS
\`\`\`

📊 *Docker Stats:*
\`\`\`
$STATS
\`\`\`"
                ;;

            "/restart "*)
                NAME=$(echo "$MSG" | cut -d' ' -f2)

                if docker ps --format '{{.Names}}' | grep -q "^$NAME$"; then
                    docker restart "$NAME"
                    send_msg "🔄 Restarted: $NAME"
                else
                    send_msg "❌ Container not found: $NAME"
                fi
                ;;

            "/logs "*)
                NAME=$(echo "$MSG" | cut -d' ' -f2)

                if docker ps --format '{{.Names}}' | grep -q "^$NAME$"; then
                    docker logs --tail 100 "$NAME" > /tmp/logs.txt
                    curl -s -X POST "$API/sendDocument" \
                        -F chat_id="$CHAT_ID" \
                        -F document=@/tmp/logs.txt >/dev/null
                else
                    send_msg "❌ Container not found: $NAME"
                fi
                ;;

            "/heal")
                /docker/maintenance/scripts/auto-heal.sh
                send_msg "🛠 Heal executed"
                ;;

            "/reboot")
                send_msg "⚠ Rebooting server..."
                log "Reboot triggered"
                sudo reboot
                ;;

            *)
                send_msg "❓ Unknown command"
                ;;
        esac

    done

    sleep 2
done
