#!/bin/bash

STATE="/docker/state"
OUT="$STATE/analysis.txt"

> $OUT

while read line; do
  NAME=$(echo $line | awk '{print $1}')
  STATUS=$(echo $line | cut -d ' ' -f2-)

  if [[ "$STATUS" == *"unhealthy"* ]]; then
    echo "$NAME UNHEALTHY" >> $OUT
  fi

  if [[ "$STATUS" == *"Restarting"* ]]; then
    echo "$NAME CRASH_LOOP" >> $OUT
  fi

done < $STATE/containers.txt
