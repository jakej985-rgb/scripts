#!/bin/bash

# 📊 Metrics Agent v3.1 — Collects docker stats
# Writes current snapshot + appends to time-series history

STATE="/docker/state"
OUT="$STATE/metrics.txt"
HISTORY="$STATE/metrics-history.csv"

# Current snapshot
docker stats --no-stream --format "{{.Name}} {{.CPUPerc}} {{.MemUsage}}" > $OUT

# Append to time-series CSV (v4.1)
TIMESTAMP=$(date +%s)

docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}}" | while IFS=',' read NAME CPU MEM; do
  CPU_VAL=$(echo $CPU | tr -d '%')
  MEM_VAL=$(echo $MEM | cut -d '/' -f1 | tr -d ' MiGBKB')

  echo "$TIMESTAMP,$NAME,$CPU_VAL,$MEM_VAL" >> $HISTORY
done

# Trim history to last 10000 lines (prevent unbounded growth)
if [ -f "$HISTORY" ]; then
  LINES=$(wc -l < "$HISTORY")
  if [ "$LINES" -gt 10000 ]; then
    tail -n 10000 "$HISTORY" > "$HISTORY.tmp" && mv "$HISTORY.tmp" "$HISTORY"
  fi
fi
