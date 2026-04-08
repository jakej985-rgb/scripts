# Migration Guide: v1 → v2

## What changed

v2 replaces all standalone scripts with an **agent-based pipeline**.
No script acts alone. Everything flows through the decision engine.

## Steps

### 1. Deploy new structure

The new directories are:
# control-plane/agents/ — Python-based agent pipeline
# dashboard/ — Flask-based web UI
# control-plane/state/ — Standardized JSON state files
# control-plane/state/logs/ — Centralized logs

### 2. Configure environment

```bash
cp .env.example .env
nano .env

# Required: VPN_USER, VPN_PASSWORD, TATTOO_DB_PASSWORD
# Optional: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
```

### 3. Remove old cron jobs

```bash
# Remove ALL old crontab entries for:
#   auto-heal.sh
#   auto-backup.sh
#   auto-fix.sh
#   auto-reboot-if-unhealthy.sh
#   auto-rollback-on-update.sh
#   predictive-ai.sh
#   log-watcher.sh
#   manage-cron.sh
crontab -e
```

### 4. Run the Control Plane

```bash
# Make runners executable
chmod +x control-plane/*.sh
chmod +x control-plane/agents/*.sh

# Start the supervisor
bash control-plane/run.sh
```

### 5. Make scripts executable

```bash
chmod +x /docker/m3tal.sh
chmod +x /docker/agents/*.sh
```

### 6. Start dashboard

```bash
cd /docker/maintenance
docker compose up -d dashboard
# Access at http://your-server:8080
```

### 7. Verify

```bash
# Run manually once to check
bash /docker/m3tal.sh

# Check state output
cat /docker/state/containers.txt
cat /docker/logs/actions.log
```

## What was removed

| Old Script                     | Replaced By                    |
|-------------------------------|--------------------------------|
| `auto-heal.sh`                | monitor + decision-engine      |
| `auto-fix.sh`                 | decision-engine + action-agent |
| `auto-reboot-if-unhealthy.sh` | removed (unsafe)               |
| `auto-rollback-on-update.sh`  | removed (unsafe)               |
| `predictive-ai.sh`            | ai-agent.sh                    |
| `ai-log-analyzer.sh`          | ai-agent.sh                    |
| `log-watcher.sh`              | monitor.sh                     |
| `auto-backup.sh`              | backup-agent.sh                |
| `api.py`                      | dashboard/server.py            |
| `install.sh`                  | manual setup (see above)       |
| `lib/env.sh`                  | direct `source connections.env`|
