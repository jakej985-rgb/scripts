#!/bin/bash

DEST="/mnt/backups/docker-configs"
DATE=$(date +%F)

mkdir -p $DEST

tar -czf $DEST/backup-$DATE.tar.gz /docker/configs

# keep last 4
ls -tp $DEST | grep .tar.gz | tail -n +5 | xargs -I {} rm -- $DEST/{}
