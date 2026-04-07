#!/bin/bash

# Backup Agent - Isolated and Safe
# Runs on schedule, keeps last 4 backups
# NEVER triggered by AI or logs

LOCKFILE="/tmp/m3tal_backup.lock"
if [ -f "$LOCKFILE" ]; then exit 0; fi
trap "rm -f $LOCKFILE" EXIT
touch $LOCKFILE

# Source connections
source "/docker/connections.env"

BASE_BACKUP_DIR="${BACKUP_DIR:-/mnt/backups/docker}"
DATE=$(date "+%Y-%m-%d_%H-%M")

for NAME in $(docker ps --format "{{.Names}}"); do
    CONTAINER_BACKUP_DIR="$BASE_BACKUP_DIR/$NAME"
    mkdir -p "$CONTAINER_BACKUP_DIR"

    for PATH_VAL in $(docker inspect -f '{{range .Mounts}}{{.Source}} {{end}}' "$NAME"); do
        # Ignore core docker lib mounts
        if [[ "$PATH_VAL" == *"/var/lib/docker"* ]]; then
            continue
        fi

        SAFE_PATH=$(echo "$PATH_VAL" | sed 's/\//_/g')
        tar -czf "$CONTAINER_BACKUP_DIR/${NAME}_${SAFE_PATH}_$DATE.tar.gz" "$PATH_VAL" 2>/dev/null
    done

    # Keep only the last 4 backups
    ls -tp "$CONTAINER_BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +5 | xargs -r rm
done
