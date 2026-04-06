#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: restore.sh <container-name>"
  exit 1
fi

NAME=$1
BACKUP_DIR="/mnt/backups/docker/$NAME"
TARGET_DIR="/docker/$NAME"

echo "Restoring $NAME..."

LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.tar.gz | head -n 1)

if [ -z "$LATEST_BACKUP" ]; then
  echo "No backups found for $NAME"
  exit 1
fi

echo "Using backup: $LATEST_BACKUP"

# Stop container
docker stop $NAME

# Remove old data
rm -rf "$TARGET_DIR"

# Restore
tar -xzf "$LATEST_BACKUP" -C /

# Start container
docker start $NAME

echo "Restore complete for $NAME"
