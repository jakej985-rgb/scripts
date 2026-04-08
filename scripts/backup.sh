#!/bin/bash
# >>> AUTO-ROOT (path-agent)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# <<< AUTO-ROOT

DEST="$REPO_ROOT/mnt/backups/docker-configs"
DATE=$(date +%F)

mkdir -p $DEST

tar -czf $DEST/backup-$DATE.tar.gz "$REPO_ROOT/docker/configs"

# keep last 4
ls -tp $DEST | grep .tar.gz | tail -n +5 | xargs -I {} rm -- $DEST/{}
