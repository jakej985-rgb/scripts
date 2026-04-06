#!/bin/bash

BASE_BACKUP_DIR="/mnt/backups/docker"
DATE=$(date "+%Y-%m-%d_%H-%M")

for NAME in $(docker ps --format "{{.Names}}"); do
  BACKUP_DIR="$BASE_BACKUP_DIR/$NAME"
  mkdir -p "$BACKUP_DIR"

  for PATH in $(docker inspect -f '{{range .Mounts}}{{.Source}} {{end}}' $NAME); do
    [[ "$PATH" == *"/var/lib/docker"* ]] && continue
    tar -czf "$BACKUP_DIR/${NAME}_$(echo $PATH | sed 's/\//_/g')_$DATE.tar.gz" "$PATH"
  done

  ls -tp "$BACKUP_DIR"/*.tar.gz | tail -n +5 | xargs -r rm
done
