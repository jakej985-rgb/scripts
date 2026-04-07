#!/bin/bash

# Action Agent - reads actions.json and executes them safely

LOCKFILE="/tmp/m3tal_action.lock"
if [ -f "$LOCKFILE" ]; then exit 0; fi
trap "rm -f $LOCKFILE" EXIT
touch $LOCKFILE

# Source connections
source "/docker/connections.env"

INFILE="/docker/state/actions.json"
LOG_FILE="/docker/logs/action.log"

if [ ! -f "$INFILE" ]; then
    exit 0
fi

log() {
    echo "$(date '+%F %T') - $1" >> "$LOG_FILE"
}

send_msg() {
    if [ ! -z "$BOT_TOKEN" ] && [ ! -z "$CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
          -d chat_id="$CHAT_ID" \
          -d text="$1" > /dev/null
    fi
}

python3 -c "
import json
import sys

try:
    with open('$INFILE') as f:
        data = json.load(f)

    for a in data.get('actions', []):
        print(f\"{a.get('command')} {a.get('target')} {a.get('reason')}\")
except Exception as e:
    pass
" | while read -r cmd target reason; do
    if [ -z "$cmd" ]; then continue; fi

    if [ "$cmd" == "restart" ]; then
        log "Executing: docker restart $target (Reason: $reason)"
        docker restart "$target" >/dev/null 2>&1
        send_msg "🔧 Restarted: $target ($reason)"

    elif [ "$cmd" == "start" ]; then
        log "Executing: docker start $target (Reason: $reason)"
        docker start "$target" >/dev/null 2>&1
        send_msg "🛠 Started: $target ($reason)"

    elif [ "$cmd" == "prune" ] && [ "$target" == "docker" ]; then
        log "Executing: docker system prune -af (Reason: $reason)"
        docker system prune -af >/dev/null 2>&1
        send_msg "🧹 Cleaned up docker system ($reason)"

    elif [ "$cmd" == "clear_temp" ]; then
        log "Executing: rm -rf /tmp/* (Reason: $reason)"
        # Safe temp clear logic can go here
        echo "Clearing temp files..."
    else
        log "Unknown command or target: $cmd $target"
    fi
done

# Clear actions once executed
echo '{"actions": []}' > "$INFILE"
