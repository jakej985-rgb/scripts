#!/bin/bash

# MED-03: Backup agent — uses REPO_ROOT and configurable DATA_DIR

# >>> AUTO-ROOT (antigravity)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# <<< AUTO-ROOT

# Standardize destination and handle spaces safely
DEST="${DATA_DIR:-/mnt}/backups/docker-configs"
DATE=$(date +%Y-%m-%d_%H%M)

echo "[BACKUP] Starting backup to $DEST..."
mkdir -p "$DEST"

# Ensure we include config, docker stacks, and critical state
# We use -C to change directory into REPO_ROOT for cleaner archive paths
tar -czf "$DEST/backup-$DATE.tar.gz" -C "$REPO_ROOT" \
  ".env" \
  "docker" \
  "control-plane/state" \
  --exclude="*.log" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "[OK] Backup created: backup-$DATE.tar.gz"
    
    # Retention: keep last 5 backups, safer cleanup pattern
    ls -t "$DEST"/backup-*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm --
    echo "[BACKUP] Retention cleanup complete."
else
    echo "[ERROR] Backup failed!"
fi
