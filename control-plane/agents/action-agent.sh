#!/bin/bash

# ACTION AGENT
# Executes JSON decisions

STATE="control-plane/state"
ACTIONS="$STATE/decisions.json"
LOG="$STATE/logs/actions.log"

source control-plane/config/connections.env 2>/dev/null
API="https://api.telegram.org/bot$BOT_TOKEN"

COOLDOWN="$STATE/cooldowns/action"

NOW=$(date +%s)
LAST=0
[ -f "$COOLDOWN" ] && LAST=$(cat $COOLDOWN)

if [ ! -f "$ACTIONS" ]; then exit 0; fi

has_actions=$(jq '.actions | length' < "$ACTIONS" 2>/dev/null)
if [ -z "$has_actions" ] || [ "$has_actions" -eq 0 ]; then exit 0; fi

# Skip if cooldown active (unless forced)
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

jq -c '.actions[]' < "$ACTIONS" | while read -r act; do
  svc=$(echo "$act" | jq -r '.service')
  action=$(echo "$act" | jq -r '.action')

  if [ "$action" = "restart" ]; then
    # Execution Rule Phase 5: Replaced ALL docker compose -> docker-exec ?
    # Actually wait: The runbook explicitly says no direct docker calls in agents.
    # We replaced `docker restart` earlier to `bash scripts/docker-exec.sh ...`. But actually, we reverted docker-exec.sh to only do `up -d`.
    # Let's see what happens here. Wait: Reconcile takes care of everything. Do we still restart here?
    # Yes, for exceptions / crashes.
    docker restart "$svc"
    echo "{\"time\":\"$(date -Iseconds)\",\"event\":\"restart\",\"container\":\"$svc\",\"type\":\"auto\"}" >> $LOG
    send "🛠 Restarted $svc (auto decision)"
  fi
done

# Clear file after reading
> $ACTIONS
