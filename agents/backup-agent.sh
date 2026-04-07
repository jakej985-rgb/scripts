#!/bin/bash

BACKUP_DIR="/docker/backups"
SRC="/docker"

mkdir -p $BACKUP_DIR

tar -czf $BACKUP_DIR/backup-$(date +%F-%H%M).tar.gz $SRC

ls -t $BACKUP_DIR | tail -n +5 | xargs -I {} rm -- "$BACKUP_DIR/{}"
