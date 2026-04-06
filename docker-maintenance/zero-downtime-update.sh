#!/bin/bash

# Zero-downtime style update (safe swap)

NAME=$1
IMAGE=$2

if [ -z "$NAME" ] || [ -z "$IMAGE" ]; then
  echo "Usage: zero-downtime-update.sh <container> <image>"
  exit 1
fi

NEW_NAME="${NAME}_new"

docker pull "$IMAGE"

docker run -d --name "$NEW_NAME" "$IMAGE"

sleep 10
STATUS=$(docker inspect --format='{{.State.Status}}' "$NEW_NAME")

if [ "$STATUS" = "running" ]; then
  docker stop "$NAME"
  docker rm "$NAME"
  docker rename "$NEW_NAME" "$NAME"
  echo "Switched to new container"
else
  docker rm -f "$NEW_NAME"
  echo "Update failed"
fi
