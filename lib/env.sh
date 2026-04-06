#!/bin/bash

# 🧠 Centralized environment loader + validation

ENV_FILE="$(dirname "$0")/../connections.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ Missing connections.env file"
  echo "Run: cp connections.env.example connections.env"
  exit 1
fi

# Load env
set -a
source "$ENV_FILE"
set +a

# Validate required vars
if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
  echo "❌ BOT_TOKEN or CHAT_ID missing in connections.env"
  exit 1
fi

# Defaults (if not set)
: ${BACKUP_DIR:="/mnt/backups/docker"}
: ${LOG_DIR:="/docker/maintenance/logs"}
: ${MAX_BACKUPS:=4}

: ${CPU_THRESHOLD:=90}
: ${MEM_THRESHOLD:=90}
: ${DISK_THRESHOLD:=85}

: ${ENABLE_AI:=false}
: ${ENABLE_AUTO_FIX:=true}
: ${ENABLE_PREDICTIVE:=true}
: ${ENABLE_AUTO_REBOOT:=false}
