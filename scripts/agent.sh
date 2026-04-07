#!/bin/bash

echo "=== M3TAL AGENT ==="

# MONITOR
containers=$(docker ps --format "{{.Names}}")

# ANALYZE + ACT
for c in $containers; do
  status=$(docker inspect --format='{{.State.Status}}' $c)

  if [ "$status" != "running" ]; then
    echo "[!] $c is down → restarting"
    docker restart $c
    
    curl -s -X POST https://api.telegram.org/bot<TOKEN>/sendMessage \
      -d chat_id=<CHAT_ID> \
      -d text="Container $c restarted"
  fi
done

echo "[✓] System checked"
