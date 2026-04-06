#!/bin/bash

LOG="/docker/maintenance/logs/auto-heal.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

echo "[$DATE] Checking container health..." >> $LOG

for CONTAINER in $(docker ps -q); do

  STATUS=$(docker inspect --format='{{.State.Health.Status}}' $CONTAINER 2>/dev/null)

  if [ "$STATUS" == "unhealthy" ]; then
    NAME=$(docker inspect --format='{{.Name}}' $CONTAINER | sed 's/\///')

    echo "[$DATE] Restarting unhealthy container: $NAME" >> $LOG

    docker restart $NAME >> $LOG 2>&1
  fi

done
