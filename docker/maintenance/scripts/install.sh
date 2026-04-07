#!/bin/bash

# 🚀 Production Installer v2 (Safe + Smart + Self-Healing Lite)

set -e

echo "🚀 Docker Auto-Maintenance Installer (Production v2)"

# -----------------------------
# Root check
# -----------------------------
if [ "$EUID" -ne 0 ]; then
  echo "⚠️ Run with sudo"
  exit 1
fi

log() { echo -e "[INFO] $1"; }
warn() { echo -e "[WARN] $1"; }
err() { echo -e "[ERROR] $1"; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

install_if_missing() {
  if ! dpkg -s "$1" >/dev/null 2>&1; then
    log "Installing $1..."
    apt-get install -y "$1"
  else
    log "$1 already installed"
  fi
}

# -----------------------------
# Update system
# -----------------------------
log "Updating apt..."
apt-get update -y

# -----------------------------
# Base deps
# -----------------------------
install_if_missing curl
install_if_missing jq

# -----------------------------
# Docker detection
# -----------------------------
DOCKER_STATUS="missing"

if have_cmd docker; then
  if docker info >/dev/null 2>&1; then
    DOCKER_STATUS="healthy"
  else
    DOCKER_STATUS="broken"
  fi
fi

log "Docker status: $DOCKER_STATUS"

# -----------------------------
# Handle Docker states
# -----------------------------

# Install if missing
if [ "$DOCKER_STATUS" = "missing" ]; then
  log "Installing Docker (fresh)"
  install_if_missing docker.io
  install_if_missing docker-compose
fi

# Repair if broken (SAFE)
if [ "$DOCKER_STATUS" = "broken" ]; then
  warn "Docker installed but not working"

  systemctl daemon-reexec || true
  systemctl daemon-reload || true

  if ! systemctl start docker 2>/dev/null; then
    warn "Docker failed to start"

    # Detect mount lock (your current issue)
    if mount | grep -q "/var/lib/docker"; then
      err "Docker mount lock detected"
      echo "👉 REQUIRED ACTION:"
      echo "   sudo reboot"
      echo "   then re-run installer"
      exit 1
    fi

    warn "Attempting safe package repair"
    apt-get install --reinstall -y docker.io docker-compose

    systemctl daemon-reload
    systemctl start docker || true
  fi
fi

# -----------------------------
# Final Docker check
# -----------------------------
if docker ps >/dev/null 2>&1; then
  log "Docker is running"
else
  warn "Docker still not running (continuing safely)"
fi

# -----------------------------
# Config setup
# -----------------------------
if [ ! -f connections.env ]; then
  cp connections.env.example connections.env
  warn "Created connections.env (edit required)"
else
  log "connections.env exists"
fi

# -----------------------------
# Permissions
# -----------------------------
chmod +x *.sh
chmod +x lib/*.sh 2>/dev/null || true

# -----------------------------
# Cron setup (idempotent)
# -----------------------------
log "Configuring cron..."
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

log "Cron installed"

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
echo "🎉 INSTALL COMPLETE (Production v2)"
echo "➡️ Next: nano connections.env"
