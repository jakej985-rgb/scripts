#!/bin/bash

CRON_TMP="/tmp/cron_jobs.txt"

# Load env (optional for logging / telegram later)
set -a
source /docker/maintenance/scripts/connections.env 2>/dev/null
set +a

log() {
  echo "$(date '+%F %T') - $1"
}

# ===== Define ALL jobs here =====
cat <<EOF > "$CRON_TMP"
# === Docker Maintenance ===

# Backup (daily 2AM)
0 2 * * * /docker/maintenance/scripts/auto-backup.sh

# Heal check (every 5 min)
*/5 * * * * /docker/maintenance/scripts/auto-heal.sh

# Telegram control loop (every minute)
* * * * * /docker/maintenance/scripts/secure-telegram-control.sh

# Alerts (every 10 min)
*/10 * * * * /docker/maintenance/scripts/log-watcher.sh

# AI summary (hourly)
0 * * * * /docker/maintenance/scripts/ai-log-analyzer.sh

# Rollback monitor (every 5 min)
*/5 * * * * /docker/maintenance/scripts/auto-rollback-on-update.sh

# Auto alert system (every 5 min)
*/5 * * * * /docker/maintenance/scripts/auto-alert.sh

EOF

# ===== Install safely =====
CURRENT=$(crontab -l 2>/dev/null)

# Remove old managed block
CLEANED=$(echo "$CURRENT" | sed '/# === Docker Maintenance ===/,$d')

# Apply new cron
( echo "$CLEANED"; cat "$CRON_TMP" ) | crontab -

log "Cron jobs updated safely"
