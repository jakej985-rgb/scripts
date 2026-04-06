#!/bin/bash

for NAME in $(docker ps -a --format "{{.Names}}"); do
  STATUS=$(docker inspect --format='{{.State.Status}}' $NAME)

  if [ "$STATUS" != "running" ]; then
    docker start $NAME
  fi
done
