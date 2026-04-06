#!/bin/bash

source /docker/scripts/docker-maintenance/notify.sh

CONTAINERS=$(docker ps --format "{{.Names}}")

for NAME in $CONTAINERS; do

  HEALTH=$(docker inspect --format='{{.State.Health.Status}}' $NAME 2>/dev/null)

  if [ "$HEALTH" == "unhealthy" ]; then
    send_telegram "⚠️ $NAME unhealthy after update, rolling back"

    /docker/scripts/docker-maintenance/rollback.sh $NAME

    send_telegram "✅ $NAME rolled back"
  fi

done
