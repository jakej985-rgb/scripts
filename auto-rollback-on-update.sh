#!/bin/bash

source connections.env

for NAME in $(docker ps --format "{{.Names}}"); do
  HEALTH=$(docker inspect --format='{{.State.Health.Status}}' $NAME 2>/dev/null)

  if [ "$HEALTH" == "unhealthy" ]; then
    curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
      -d chat_id="$CHAT_ID" \
      -d text="Rolling back $NAME"

    ./rollback.sh $NAME
  fi
done
