#!/bin/bash

LOG="/docker/maintenance/logs/auto-backup.log"
BASE_BACKUP_DIR="/mnt/backups/docker"
DATE=$(date "+%Y-%m-%d_%H-%M")

echo "[$DATE] Starting AUTO backup..." >> $LOG

# Get running containers
CONTAINERS=$(docker ps --format "{{.Names}}")

for NAME in $CONTAINERS; do

  echo "Processing $NAME..." >> $LOG

  BACKUP_DIR="$BASE_BACKUP_DIR/$NAME"
  mkdir -p "$BACKUP_DIR"

  # Get mount paths
  MOUNTS=$(docker inspect -f '{{range .Mounts}}{{.Source}} {{end}}' $NAME)

  for PATH_TO_BACKUP in $MOUNTS; do

    # Skip system paths
    if [[ "$PATH_TO_BACKUP" == *"/var/lib/docker"* ]]; then
      continue
    fi

    SAFE_NAME=$(echo $PATH_TO_BACKUP | sed 's/\//_/g')

    echo "Backing up $NAME -> $PATH_TO_BACKUP" >> $LOG

    tar -czf "$BACKUP_DIR/${NAME}_${SAFE_NAME}_$DATE.tar.gz" "$PATH_TO_BACKUP" >> $LOG 2>&1

  done

  # Keep only latest 4 backups
  ls -tp "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +5 | while read file; do
    echo "Deleting old backup: $file" >> $LOG
    rm -- "$file"
  done

done

echo "[$DATE] AUTO backup complete" >> $LOG
echo "" >> $LOG
