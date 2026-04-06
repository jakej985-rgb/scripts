#!/bin/bash

set -e

echo "🚀 Docker Auto-Maintenance Installer"

# -----------------------------
# Check root
# -----------------------------
if [ "$EUID" -ne 0 ]; then
  echo "⚠️ Please run with sudo"
  exit 1
fi

# -----------------------------
# Function: install if missing
# -----------------------------
install_if_missing() {
  if ! dpkg -s "$1" >/dev/null 2>&1; then
    echo "📦 Installing $1..."
    apt install -y "$1"
  else
    echo "✅ $1 already installed"
  fi
}

# -----------------------------
# Detect & fix Docker conflicts
# -----------------------------
if dpkg -l | grep -q containerd.io && dpkg -l | grep -q containerd; then
  echo "⚠️ Docker conflict detected (containerd vs containerd.io)"
  echo "🧹 Fixing..."

  apt remove -y containerd containerd.io docker docker-engine docker.io || true
  apt autoremove -y
fi

# -----------------------------
# Update apt
# -----------------------------
echo "🔄 Updating package list..."
apt update

# -----------------------------
# Install dependencies
# -----------------------------
install_if_missing docker.io
install_if_missing docker-compose
install_if_missing jq
install_if_missing curl

# -----------------------------
# Enable Docker
# -----------------------------
systemctl enable docker
systemctl start docker

# -----------------------------
# Verify Docker works
# -----------------------------
if ! docker ps >/dev/null 2>&1; then
  echo "❌ Docker failed to start"
  exit 1
fi

echo "✅ Docker is running"

# -----------------------------
# Setup config
# -----------------------------
if [ ! -f connections.env ]; then
  echo "📄 Creating connections.env"
  cp connections.env.example connections.env
  echo "⚠️ Edit connections.env before running system"
else
  echo "✅ connections.env exists"
fi

# -----------------------------
# Permissions
# -----------------------------
chmod +x *.sh
chmod +x lib/*.sh 2>/dev/null || true

# -----------------------------
# Cron (deduplicated)
# -----------------------------
echo "⏰ Setting up cron jobs..."

CRON_TMP=$(mktemp)

# Remove old entries
crontab -l 2>/dev/null | grep -v "$(pwd)" > "$CRON_TMP" || true

cat <<EOF >> "$CRON_TMP"
0 2 1 * * $(pwd)/auto-backup.sh
*/5 * * * * $(pwd)/auto-heal.sh
*/5 * * * * $(pwd)/auto-fix.sh
*/5 * * * * $(pwd)/learning-mode.sh
*/5 * * * * $(pwd)/predictive-ai.sh
*/5 * * * * $(pwd)/auto-rollback-on-update.sh
*/10 * * * * $(pwd)/log-watcher.sh
0 * * * * $(pwd)/ai-log-analyzer.sh
*/10 * * * * $(pwd)/auto-reboot-if-unhealthy.sh
@reboot $(pwd)/post-reboot-check.sh
* * * * * $(pwd)/secure-telegram-control.sh
EOF

crontab "$CRON_TMP"
rm "$CRON_TMP"

echo "✅ Cron installed"

# -----------------------------
# Start monitoring (if present)
# -----------------------------
if [ -f monitoring-compose.yml ]; then
  docker compose -f monitoring-compose.yml up -d || true
fi

if [ -f node-exporter-compose.yml ]; then
  docker compose -f node-exporter-compose.yml up -d || true
fi

# -----------------------------
# Done
# -----------------------------
echo ""
echo "🎉 INSTALL COMPLETE"
echo "➡️ Next step:"
echo "nano connections.env"
echo ""