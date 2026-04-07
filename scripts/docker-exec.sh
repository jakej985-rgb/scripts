#!/bin/bash

STACK=$1

echo "[EXEC] $STACK"
docker compose -f docker/$STACK/docker-compose.yml up -d
