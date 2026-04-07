#!/bin/bash

# 🌐 Node Agent v5.1 — Heartbeat + Status Broadcaster
# Broadcasts presence to master via heartbeat registration
# Also exposes local container status for cluster queries

source /docker/connections.env 2>/dev/null

MASTER="${MASTER_URL:-http://localhost:8888}"
NODE_NAME=$(hostname)
NODE_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
NODE_PORT="${NODE_PORT:-8080}"

# Update local status file
docker ps --format "{{.Names}} {{.Status}}" > /docker/state/node-status.txt

# Send heartbeat to master (non-blocking, fail-safe)
curl -s --max-time 3 -X POST "$MASTER/api/register" \
  -d "name=$NODE_NAME" \
  -d "ip=$NODE_IP" \
  -d "port=$NODE_PORT" > /dev/null 2>&1 || true
