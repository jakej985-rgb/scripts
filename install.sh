#!/bin/bash

echo "🚀 Installing M3TAL Control Plane..."

# Create core directories
mkdir -p /docker/{state,logs,agents,config,dashboard}

# Copy structure to /docker/
cp -r agents/* /docker/agents/
cp -r dashboard/* /docker/dashboard/
cp -r config/* /docker/config/
cp .env /docker/connections.env 2>/dev/null || true
cp m3tal.sh /docker/
cp VERSION /docker/ 2>/dev/null || true

chmod +x /docker/agents/*.sh /docker/m3tal.sh

echo "Installing dependencies..."
apt update && apt install -y jq curl python3 python3-pip

# Install yq for reconcile.sh
if ! command -v yq &> /dev/null; then
    echo "Installing yq..."
    wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
    chmod a+x /usr/local/bin/yq
fi

pip3 install flask requests

echo "Setting cron jobs..."

(crontab -l 2>/dev/null | grep -v "m3tal.sh"; echo "* * * * * /docker/m3tal.sh") | crontab -
(crontab -l 2>/dev/null | grep -v "backup-agent.sh"; echo "0 3 * * * /docker/agents/backup-agent.sh") | crontab -

echo "Checking system..."
command -v docker >/dev/null || { echo "Docker missing"; exit 1; }
command -v jq >/dev/null || { echo "jq missing"; exit 1; }
command -v yq >/dev/null || { echo "yq missing"; exit 1; }

echo "✅ Installation complete"
echo "👉 Configure /docker/connections.env and start the dashboard with: cd /docker/maintenance && docker compose up -d dashboard"
