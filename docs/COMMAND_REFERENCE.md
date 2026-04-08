# 🛠️ M3TAL Command Reference

This is a "Cheat Sheet" for managing and troubleshooting your M3TAL Media Server via the command line.

---

## 🚀 Core M3TAL Commands

Run these from the repository root directory.

| Task | Command |
| :--- | :--- |
| **Install/Setup** | `./install.sh` |
| **Start Control Plane** | `bash control-plane/run.sh` |
| **Reset State Machine** | `bash control-plane/init.sh` |
| **Backup Everything** | `bash scripts/backup.sh` |
| **Restore from Backup** | `bash scripts/restore.sh` |

---

## 📜 Log Reading Commands

Monitoring the "thoughts" of the agents in real-time.

### Watch a specific agent live

```bash
tail -f control-plane/state/logs/monitor.log
tail -f control-plane/state/logs/reconcile.log
tail -f control-plane/state/logs/decision.log
```

### Search for errors across all logs

```bash
grep -r "ERROR" control-plane/state/logs/
```

### Check the last 50 actions taken by the system

```bash
tail -n 50 control-plane/state/logs/reconcile.log
```

---

## 🐳 Docker Troubleshooting

Sometimes you need to look at the containers directly.

| Task | Command |
| :--- | :--- |
| **List all containers** | `docker ps -a` |
| **List running apps** | `docker ps` |
| **View an app's logs** | `docker logs <container_name>` |
| **Follow an app's logs** | `docker logs -f <container_name>` |
| **Stop a container** | `docker stop <container_name>` |
| **Restart a container** | `docker restart <container_name>` |
| **See container usage** | `docker stats` |

---

## 🧪 Debugging Agents Manually

If an agent is failing, you can run it manually in the foreground to see the error output:

### Check Monitor

```bash
python3 control-plane/agents/monitor.py
```

### Check Metrics

```bash
python3 control-plane/agents/metrics.py
```

### Check Reconciler

```bash
python3 control-plane/agents/reconcile.py
```

---

## 💾 Storage & Filesystem

### Check the Health Score via CLI

```bash
cat control-plane/state/health_report.json | jq
```

### Check remaining disk space on your media drive

```bash
df -h | grep /mnt
```

### Fix storage permissions

```bash
sudo chown -R $USER:$USER .
chmod -R 775 control-plane/state/
```

---

## 🌐 Network

### See what is running on port 8080 (Dashboard)

```bash
sudo lsof -i :8080
```

### Check connectivity to the primary node

```bash
ping <leader_ip>
```
