#!/bin/bash

# M3TAL DISASTER RECOVERY - Restore Agent
# v1.1.0

# >>> AUTO-ROOT (antigravity)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# <<< AUTO-ROOT

# Default to latest backup if no file provided
BACKUP_FILE=$1
BACKUP_DIR="${DATA_DIR:-/mnt}/backups/docker-configs"

echo "=== M3TAL RESTORE WIZARD ==="

if [ -z "$BACKUP_FILE" ]; then
    echo "[LOOKUP] Searching for latest backup in $BACKUP_DIR..."
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/backup-*.tar.gz 2>/dev/null | head -n 1)
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] No backup file found. Usage: bash restore.sh [path_to_tar.gz]"
    exit 1
fi

echo "[TARGET] Restoring from: $BACKUP_FILE"
read -p "⚠️ This will OVERWRITE existing config and docker files in $REPO_ROOT. Continue? (y/n): " CONFIRM
[ "$CONFIRM" != "y" ] && exit 1

# Extracting
echo "[RESTORE] Extracting files..."
tar -xzvf "$BACKUP_FILE" -C "$REPO_ROOT"

if [ $? -eq 0 ]; then
    echo "[OK] Restore complete."
    echo "[OK] Re-running init to refresh state..."
    bash "$REPO_ROOT/control-plane/init.sh"
    echo "[DONE] System ready. Run 'bash control-plane/run.sh' to resume."
else
    echo "[ERROR] Restore failed during extraction."
    exit 1
fi
