#!/bin/bash

echo "==== M3TAL AGENT START ===="

echo "[1] Updating containers..."
docker compose -f docker/core/docker-compose.yml pull
docker compose -f docker/media/docker-compose.yml pull
docker compose -f docker/apps/tattoo-app/docker-compose.yml pull

echo "[2] Restarting stacks..."
docker compose -f docker/core/docker-compose.yml up -d
docker compose -f docker/media/docker-compose.yml up -d
docker compose -f docker/apps/tattoo-app/docker-compose.yml up -d

echo "[3] Running backup..."
bash docker/scripts/backup.sh

echo "==== DONE ===="
