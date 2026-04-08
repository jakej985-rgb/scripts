# 🔍 Diagnostics & Troubleshooting Guide

If something goes wrong with your M3TAL Media Server, follow this guide to find and fix the error.

---

## 🚦 First Steps: The Dashboard
The quickest way to diagnose an issue is the **Health Score** in the Dashboard.
*   **100%**: System is perfect.
*   **85% - 99%**: Warning. Small issue (e.g., a stalled log or a transient spike).
*   **Below 60%**: Critical. A core agent has crashed or a primary container is down.

---

## 📂 The "State" Directory
The `control-plane/state/` folder is the "Single Source of Truth." 

### 1. Checking the Logs
Every agent logs its activity to `control-plane/state/logs/`.
*   `reconcile.log`: See if restarts are failing.
*   `anomaly.log`: See what the system thinks is "wrong."
*   `leader.log`: Check if this node thinks it is the Leader or a Follower.
*   `supervisor.log`: Check if agents are crashing repeatedly.

**Pro-Tip**: Use `tail -f` to watch a log in real-time:
```bash
tail -f control-plane/state/logs/reconcile.log
```

### 2. Inspecting the State Files
The JSON files in `state/` show exactly what the agents are seeing:
*   `health.json`: The raw health status of every container.
*   `decisions.json`: The pending actions the system is about to take.
*   `metrics.json`: The latest CPU and Memory stats.

---

## ⚠️ Common Issues

### "My container won't stay started!"
1. Check `reconcile.log`. It might show a Docker error (e.g., port already in use).
2. Check `decision.py`'s cooldowns. If an app crashes too many times, M3TAL might put it on a 10-minute "cooldown" to prevent log spam.

### "Dashboard says 'Agent Stalled'"
1. This means an agent hasn't updated its heartbeat in over 2 minutes.
2. Check `control-plane/run.sh` to see if the supervisor is trying to restart it.
3. Check the specific agent's log. It might have a syntax error or a missing Python library.

### "Permission Denied"
M3TAL needs permission to talk to the Docker socket.
```bash
sudo usermod -aG docker $USER
newgrp docker
```

---

## 🚑 Full Reset
If the state machine gets into a weird loop, you can safely reset all non-persistent state:
```bash
bash control-plane/init.sh
```
This will recreate missing files and clear any "stuck" decisions.
