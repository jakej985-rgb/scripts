#!/bin/bash

# Rollback container using latest backup

NAME=$1
BACKUP_DIR="/mnt/backups/docker/$NAME"
TARGET_DIR="/docker/$NAME"

if [ -z "$NAME" ]; then
  echo "Usage: rollback.sh <container>"
  exit 1
fi

LATEST=$(ls -t "$BACKUP_DIR"/*.tar.gz | head -n 1)

if [ -z "$LATEST" ]; then
  echo "No backup found"
  exit 1
fi

echo "Rolling back $NAME using $LATEST"

docker stop $NAME
rm -rf "$TARGET_DIR"
tar -xzf "$LATEST" -C /
docker start $NAME

echo "Rollback complete"
