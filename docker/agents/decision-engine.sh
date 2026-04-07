#!/bin/bash

# Decision Engine Agent - reads from analyzer.json, checks rules/cooldowns/retries, writes to actions.json

LOCKFILE="/tmp/m3tal_decision.lock"
if [ -f "$LOCKFILE" ]; then exit 0; fi
trap "rm -f $LOCKFILE" EXIT
touch $LOCKFILE

# Source connections
source "/docker/connections.env"

INFILE="/docker/state/analyzer.json"
OUTFILE="/docker/state/actions.json"
COOLDOWN_DIR="/docker/state/cooldowns"
RETRIES_DIR="/docker/state/retries"
MAX_RETRIES=3

mkdir -p "$COOLDOWN_DIR" "$RETRIES_DIR"

if [ ! -f "$INFILE" ]; then
    echo '{"actions": []}' > "$OUTFILE"
    exit 0
fi

ACTIONS="["
FIRST=1

add_action() {
    local cmd="$1"
    local target="$2"
    local reason="$3"
    if [ $FIRST -eq 0 ]; then
        ACTIONS="$ACTIONS,"
    fi
    FIRST=0
    ACTIONS="$ACTIONS {\"command\": \"$cmd\", \"target\": \"$target\", \"reason\": \"$reason\"}"
}

send_alert() {
    local text="$1"
    if [ ! -z "$BOT_TOKEN" ] && [ ! -z "$CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
          -d chat_id="$CHAT_ID" \
          -d text="$text" > /dev/null
    else
        echo "ALERT: $text"
    fi
}

check_cooldown() {
    local key="$1"
    local cooldown_time="$2"
    local cf="$COOLDOWN_DIR/$key"
    if [ -f "$cf" ] && [ $(($(date +%s) - $(cat "$cf"))) -lt "$cooldown_time" ]; then
        return 1 # in cooldown
    fi
    return 0 # not in cooldown
}

set_cooldown() {
    local key="$1"
    date +%s > "$COOLDOWN_DIR/$key"
}

get_retries() {
    local key="$1"
    local rf="$RETRIES_DIR/$key"
    if [ -f "$rf" ]; then
        cat "$rf"
    else
        echo "0"
    fi
}

increment_retries() {
    local key="$1"
    local count=$(get_retries "$key")
    echo "$((count + 1))" > "$RETRIES_DIR/$key"
}

reset_retries() {
    local key="$1"
    rm -f "$RETRIES_DIR/$key"
}

# Parse recommendations
python3 -c "
import json
import sys

try:
    with open('$INFILE') as f:
        data = json.load(f)

    for r in data.get('recommendations', []):
        print(f\"{r.get('action')} {r.get('target')} {r.get('reason')}\")
except Exception as e:
    pass
" | while read -r action target reason; do
    if [ -z "$action" ]; then continue; fi

    # Rules
    if [ "$action" == "healthy" ]; then
        reset_retries "restart_$target"

    elif [ "$action" == "alert" ]; then
        if check_cooldown "alert_$target" 300; then
            if [ "$reason" == "permission_issue" ]; then
                send_alert "⚠️ Permission issue detected for $target. Restarting NOT helpful. Please check manually."
            else
                send_alert "⚠️ Alert for $target: $reason"
            fi
            set_cooldown "alert_$target"
        fi

    elif [ "$action" == "start" ] || [ "$action" == "restart" ]; then
        retries=$(get_retries "restart_$target")
        if [ "$retries" -ge "$MAX_RETRIES" ]; then
            if check_cooldown "alert_max_retries_$target" 900; then
                send_alert "❌ $target failed $MAX_RETRIES times. Suggested fix: Check logs. Approve restart? (yes/no)"
                set_cooldown "alert_max_retries_$target"
            fi
        else
            if check_cooldown "action_restart_$target" 60; then
                increment_retries "restart_$target"
                set_cooldown "action_restart_$target"
                add_action "$action" "$target" "$reason"
            fi
        fi

    elif [ "$action" == "prune" ]; then
        if check_cooldown "action_prune" 3600; then
            set_cooldown "action_prune"
            add_action "prune" "docker" "$reason"
        fi
    fi
done

ACTIONS="$ACTIONS]"

cat > "$OUTFILE" <<EOF
{
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "actions": $ACTIONS
}
EOF
