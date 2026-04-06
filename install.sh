#!/bin/bash

source "$(dirname "$0")/lib/env.sh"

set -e

echo "🚀 Installing Docker Auto-Maintenance System"

# Install deps
sudo apt update
sudo apt install -y docker.io docker-compose jq
sudo systemctl enable docker

# Setup env
if [ ! -f connections.env ]; then
  cp connections.env.example connections.env
  echo "⚠️ Edit connections.env with your BOT_TOKEN and CHAT_ID"
fi

# Permissions
chmod +x *.sh

# Setup cron (append safely)
(crontab -l 2>/dev/null; echo "0 2 1 * * $(pwd)/auto-backup.sh") | crontab -
(crontab -l 2>/dev/null; echo "*/5 * * * * $(pwd)/auto-heal.sh") | crontab -
(crontab -l 2>/dev/null; echo "* * * * * $(pwd)/secure-telegram-control.sh") | crontab -
(crontab -l 2>/dev/null; echo "*/10 * * * * $(pwd)/log-watcher.sh") | crontab -
(crontab -l 2>/dev/null; echo "0 * * * * $(pwd)/ai-log-analyzer.sh") | crontab -
(crontab -l 2>/dev/null; echo "*/5 * * * * $(pwd)/auto-rollback-on-update.sh") | crontab -

# Start monitoring
docker compose -f monitoring-compose.yml up -d
docker compose -f node-exporter-compose.yml up -d

echo "✅ Install complete"
