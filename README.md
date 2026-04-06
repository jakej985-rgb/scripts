# 🚀 Docker Auto-Maintenance System (Clean Version)

All scripts are now in the **root folder** for simplicity.

## Setup

```bash
chmod +x *.sh
crontab -e
```

## Core Scripts

- auto-backup.sh → backups (keeps 4)
- auto-heal.sh → restarts broken containers
- secure-telegram-control.sh → remote control
- log-watcher.sh → alerts
- ai-log-analyzer.sh → summaries
- rollback.sh → restore container
- zero-downtime-update.sh → safe updates

## Monitoring

```bash
docker compose -f monitoring-compose.yml up -d
```

## Notes

- Old folder structure can be ignored
- Everything needed is now in root
