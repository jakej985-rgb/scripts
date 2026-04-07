# Migration Guide: v1 → v2

## What changed

v2 replaces all standalone scripts with an **agent-based pipeline**.
No script acts alone. Everything flows through the decision engine.

## Steps

### 1. Deploy new structure

```bash
# The new directories are already in the repo:
# /docker/agents/    — all 7 agent scripts
# /docker/dashboard/ — web UI
# /docker/state/     — runtime state (locks, cooldowns, retries)
# /docker/logs/      — centralized logs
```

### 2. Configure environment

```bash
cp /docker/connections.env.example /docker/connections.env
nano /docker/connections.env

# Required: BOT_TOKEN, CHAT_ID
# Optional: ENABLE_AI=true, OLLAMA_HOST
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

### 4. Add new cron jobs

```bash
# Agent pipeline — every minute
* * * * * /docker/m3tal.sh

# Backups — daily at 3 AM
0 3 * * * /docker/agents/backup-agent.sh
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
