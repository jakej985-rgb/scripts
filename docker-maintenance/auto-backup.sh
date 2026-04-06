#!/bin/bash

LOG="/docker/maintenance/logs/auto-backup.log"
BASE_BACKUP_DIR="/mnt/backups/docker"
DATE=$(date "+%Y-%m-%d_%H-%M")

CONTAINERS=$(docker ps --format "{{.Names}}")

for NAME in $CONTAINERS; do
  BACKUP_DIR="$BASE_BACKUP_DIR/$NAME"
  mkdir -p "$BACKUP_DIR"

  MOUNTS=$(docker inspect -f '{{range .Mounts}}{{.Source}} {{end}}' $NAME)

  for PATH_TO_BACKUP in $MOUNTS; do
    if [[ "$PATH_TO_BACKUP" == *"/cache"* ]] || \
       [[ "$PATH_TO_BACKUP" == *"/tmp"* ]] || \
       [[ "$PATH_TO_BACKUP" == *"/logs"* ]] || \
       [[ "$PATH_TO_BACKUP" == *"/var/lib/docker"* ]]; then
      continue
    fi

    SAFE_NAME=$(echo $PATH_TO_BACKUP | sed 's/\//_/g')
    tar -czf "$BACKUP_DIR/${NAME}_${SAFE_NAME}_$DATE.tar.gz" "$PATH_TO_BACKUP"
  done

  ls -tp "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +5 | xargs -r rm

done
