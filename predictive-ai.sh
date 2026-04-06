#!/bin/bash

# 🧠 Predictive AI (heuristic-based)
# Detects trends and warns before failure

source "$(dirname "$0")/lib/env.sh"

HOST=$(hostname)

send() {
  curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
    -d chat_id="$CHAT_ID" \
    -d text="$1" > /dev/null
}

# CPU trend (3 samples)
CPU1=$(top -bn1 | grep "Cpu(s)" | awk '{print $2+$4}')
sleep 2
CPU2=$(top -bn1 | grep "Cpu(s)" | awk '{print $2+$4}')
sleep 2
CPU3=$(top -bn1 | grep "Cpu(s)" | awk '{print $2+$4}')

# Memory
MEM=$(free | awk '/Mem:/ {printf("%.0f", $3/$2 * 100)}')

# Disk
DISK=$(df / | awk 'NR==2 {print $5}' | tr -d '%')

# Heuristics
if (( $(echo "$CPU1 < $CPU2" | bc -l) )) && (( $(echo "$CPU2 < $CPU3" | bc -l) )) && (( $(echo "$CPU3 > 80" | bc -l) )); then
  send "⚠️ [$HOST] CPU trending upward (possible runaway process)"
fi

if [ "$MEM" -gt "${MEM_THRESHOLD:-85}" ]; then
  send "⚠️ [$HOST] Memory high ($MEM%) – possible leak"
fi

if [ "$DISK" -gt "${DISK_THRESHOLD:-85}" ]; then
  send "⚠️ [$HOST] Disk usage high ($DISK%) – may fill soon"
fi
