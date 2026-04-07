#!/bin/bash

# 🔍 Anomaly Detection Agent v3.1 — CPU/MEM threshold detection
# Reads metrics.txt and flags anomalies for the decision engine

STATE="control-plane/state"
METRICS="$STATE/metrics.txt"
ANOM="$STATE/anomalies.json"

source /docker/connections.env 2>/dev/null

CPU_LIMIT="${CPU_THRESHOLD:-90}"
MEM_LIMIT_MB="${MEM_LIMIT:-800}"

> $ANOM

if [ ! -f "$METRICS" ]; then exit 0; fi

while read line; do
  NAME=$(echo $line | awk '{print $1}')
  CPU=$(echo $line | awk '{print $2}' | tr -d '%')
  MEM_RAW=$(echo $line | awk '{print $3}')

  # Normalize memory to MiB
  MEM=$(echo $MEM_RAW | cut -d '/' -f1 | tr -d ' MiB')
  if echo "$MEM_RAW" | grep -qi "GiB"; then
    MEM=$(echo "$MEM_RAW" | cut -d '/' -f1 | tr -d ' GiB' | awk '{printf "%.0f", $1 * 1024}')
  fi

  # CPU anomaly
  if [ -n "$CPU" ] && [ "${CPU%.*}" -gt "$CPU_LIMIT" ] 2>/dev/null; then
    echo "{\"name\":\"$NAME\", \"issue\":\"HIGH_CPU\", \"value\":\"$CPU%\"}" >> $ANOM
  fi

  # Memory anomaly
  if [ -n "$MEM" ] && [ "${MEM%.*}" -gt "$MEM_LIMIT_MB" ] 2>/dev/null; then
    echo "{\"name\":\"$NAME\", \"issue\":\"HIGH_MEM\", \"value\":\"${MEM}MiB\"}" >> $ANOM
  fi

done < $METRICS
