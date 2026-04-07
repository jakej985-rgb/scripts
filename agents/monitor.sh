#!/bin/bash

STATE="/docker/state"
LOG="/docker/logs/monitor.log"

docker ps --format "{{.Names}} {{.Status}}" > $STATE/containers.txt

df -h > $STATE/disk.txt

echo "$(date) Monitor run" >> $LOG
