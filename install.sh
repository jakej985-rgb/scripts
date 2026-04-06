#!/bin/bash

set -e

echo "🚀 Docker Auto-Maintenance Installer (Self-Healing Edition)"

# -----------------------------
# Root check
# -----------------------------
if [ "$EUID" -ne 0 ]; then
  echo "⚠️ Run with sudo"
  exit 1
fi

# -----------------------------
# Install if missing
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
# FULL Docker repair
# -----------------------------
fix_docker_install() {
  echo "🧠 Running FULL Docker repair..."

  systemctl stop docker 2>/dev/null || true

  apt remove -y docker docker.io docker-compose containerd containerd.io || true
  apt autoremove -y
  apt clean

  rm -rf /var/lib/docker
  rm -rf /var/lib/containerd

  apt update
  apt install -y docker.io docker-compose

  systemctl daemon-reexec
  systemctl daemon-reload
}

# -----------------------------
# Check Docker service exists
# -----------------------------
check_docker_service() {
  if ! systemctl list-unit-files | grep -q docker.service; then
    echo "❌ Docker service missing → repairing"
    fix_docker_install
  fi
}

# -----------------------------
# Start Docker safely
# -----------------------------
start_docker() {
  if ! systemctl start docker 2>/dev/null; then
    echo "⚠️ Docker failed to start → repairing"
    fix_docker_install

    systemctl enable docker
    systemctl start docker
  fi
}

# -----------------------------
# Verify Docker works
# -----------------------------
verify_docker() {
  if ! docker ps >/dev/null 2>&1; then
    echo "❌ Docker still broken after repair"
    echo "👉 Run: journalctl -xeu docker.service"
    exit 1
  fi
}

# -----------------------------
# Detect conflicts
# -----------------------------
if dpkg -l | grep -q containerd.io && dpkg -l | grep -q containerd; then
  echo "⚠️ Conflict detected (containerd vs containerd.io)"
  fix_docker_install
fi

# -----------------------------
# Base deps
# -----------------------------
apt update

install_if_missing jq
install_if_missing curl

# -----------------------------
# Docker self-healing flow
# -----------------------------
check_docker_service
start_docker
verify_docker

echo "✅ Docker healthy"

# -----------------------------
# Config setup
# -----------------------------
if [ ! -f connections.env ]; then
  cp connections.env.example connections.env
  echo "⚠️ Edit connections.env before use"
fi

# -----------------------------
# Permissions
# -----------------------------
chmod +x *.sh
chmod +x lib/*.sh 2>/dev/null || true

# -----------------------------
# Cron (clean + deduped)
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

echo "⏰ Cron installed"

# -----------------------------
# Monitoring
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
echo "🎉 INSTALL COMPLETE (SELF-HEALED)"
echo "➡️ Next: nano connections.env"
echo ""