#!/bin/bash

# docker-exec.sh
# Execute docker commands abstracted from the agents

CMD=$1
TARGET=$2

if [ "$CMD" = "stack-up" ]; then
    echo "[DOCKER] Applying stack: $TARGET"
    docker compose -f docker/$TARGET/docker-compose.yml up -d
elif [ "$CMD" = "stop" ]; then
    echo "[DOCKER] Stopping container: $TARGET"
    docker stop $TARGET
elif [ "$CMD" = "restart" ]; then
    echo "[DOCKER] Restarting container: $TARGET"
    docker restart $TARGET
else
    # Default behavior for Phase 5.1 compatibility
    echo "[DOCKER] Applying stack: $1"
    docker compose -f docker/$1/docker-compose.yml up -d
fi
