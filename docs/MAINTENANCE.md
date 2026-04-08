# 🛠️ M3TAL Maintenance Runbook (v1.2.0)

This document provides high-level DevOps procedures for maintaining and updating the M3TAL Media Server.

---

## 🔄 System Updates

### 1. Updating M3TAL Core

To pull the latest agent logic and dashboard updates:

```bash
git pull
# Re-run init to ensure new state migrations are applied
bash control-plane/init.sh
# Restart the supervisor
pkill -f run.sh
bash control-plane/run.sh &
```

### 2. Updating Docker Containers

The M3TAL registry will automatically detect image updates on the next restart.

```bash
# Pull all new images
docker compose -f docker/media/docker-compose.yml pull
# Redeploy
docker compose -f docker/media/docker-compose.yml up -d
```

---

## 🧹 Housekeeping

### Manual Log Truncation

If agent logs grow too large despite rotation, you can clear them safely:

```bash
# Clear all agent logs
truncate -s 0 control-plane/state/logs/*.log
```

### State Reset (The Nuclear Option)

If the state machine enters an unrecoverable loop, reset the cluster state:

```bash
bash control-plane/init.sh --force
```

---

## 🏮 Manual Overrides

### Stopping the Autonomous Plane

To stop agents without stopping the media services:

```bash
pkill -f "python3 control-plane/agents/"
```

### Forcing Leader Election

To force a specific node to take over as primary:

```bash
echo "YOUR_HOSTNAME" > control-plane/state/leader.txt
```

---

## 📡 Disaster Recovery (DR)

Check your backup status:

```bash
ls -lh /mnt/backups/docker-configs/
```

Verify `backup.sh` is in your crontab:

```bash
crontab -l | grep backup.sh
```
