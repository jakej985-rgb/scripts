#!/bin/bash

STACK=$1

echo "[EXEC] Applying $STACK"
docker compose -f docker/$STACK/docker-compose.yml up -d
