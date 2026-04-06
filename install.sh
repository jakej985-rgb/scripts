#!/bin/bash

set -e

echo "🚀 Docker Auto-Maintenance Installer (SAFE MODE)"

# -----------------------------
# Root check
# -----------------------------
if [ "$EUID" -ne 0 ]; then
  echo "⚠️ Run with sudo"
  exit 1
fi

have_cmd() { command -v "$1" >/dev/null 2>&1; }

install_if_missing() {
  if ! dpkg -s "$1" >/dev/null 2>&1; then
    echo "📦 Installing $1..."
    apt-get install -y "$1"
  else
    echo "✅ $1 already installed"
  fi
}

echo "🔄 Updating packages..."
apt-get update -y

# -----------------------------
# Base dependencies
# -----------------------------
install_if_missing curl
install_if_missing jq

# -----------------------------
# Docker detection
# -----------------------------
DOCKER_OK=false

if have_cmd docker; then
  if docker info >/dev/null 2>&1; then
    DOCKER_OK=true
    echo "✅ Docker already working"
  else
    echo "⚠️ Docker installed but not running"
  fi
else
  echo "ℹ️ Docker not installed"
fi

# -----------------------------
# Safe Docker fix (NO DATA DELETE)
# -----------------------------
if [ "$DOCKER_OK" = false ]; then
  echo "🔧 Attempting SAFE Docker repair..."

  # Only fix known conflict
  if dpkg -l | grep -q containerd.io && dpkg -l | grep -q containerd; then
    echo "⚠️ containerd conflict → removing only containerd"
    apt-get remove -y containerd || true
  fi

  install_if_missing docker.io
  install_if_missing docker-compose

  systemctl daemon-reexec || true
  systemctl daemon-reload || true
  systemctl enable docker || true

  if ! systemctl start docker 2>/dev/null; then
    echo ""
    echo "⚠️ Docker failed to start"
    echo "👉 NOT forcing cleanup to avoid data loss"
    echo "👉 If broken, run manual reset:"
    echo "   sudo systemctl stop docker"
    echo "   sudo rm -rf /var/lib/docker"
    echo ""
  fi
fi

# -----------------------------
# Verify (non-fatal)
# -----------------------------
if docker ps >/dev/null 2>&1; then
  echo "✅ Docker running"
else
  echo "⚠️ Docker not running yet (installer continues safely)"
fi

# -----------------------------
# Config setup
# -----------------------------
if [ ! -f connections.env ]; then
  cp connections.env.example connections.env
  echo "⚠️ Created connections.env (edit it)"
else
  echo "✅ connections.env exists"
fi

# -----------------------------
# Permissions
# -----------------------------
chmod +x *.sh
chmod +x lib/*.sh 2>/dev/null || true

# -----------------------------
# Cron (idempotent)
# -----------------------------
CRON_TMP=$(mktemp)
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

echo "⏰ Cron configured"

# -----------------------------
# Optional monitoring
# -----------------------------
if docker ps >/dev/null 2>&1; then
  if [ -f monitoring-compose.yml ]; then
    docker compose -f monitoring-compose.yml up -d || true
  fi

  if [ -f node-exporter-compose.yml ]; then
    docker compose -f node-exporter-compose.yml up -d || true
  fi
fi

# -----------------------------
# Done
# -----------------------------
echo ""
echo "🎉 INSTALL COMPLETE (SAFE)"
echo "➡️ Next: nano connections.env"