# Migration Guide: v1.1 → v1.2

This guide covers the transition from the legacy script-based orchestration to the **v1.2.0 Autonomous Agent Pipeline**.

---

## 🏗️ What changed

* **Decentralized Execution**: All shell scripts have been replaced by Python-based agents.
* **State Isolation**: Agents no longer write to a shared global file; they use segmented files in `control-plane/state/health/` to prevent data corruption.
* **Standardized Supervisor**: The control plane is now managed by a single `run.sh` supervisor with built-in crash protection.

---

## 🚀 Migration Steps

### 1. Repository Alignment

Ensure you are in the repository root. M3TAL now uses **AUTO-ROOT** detection, so paths are resolved relative to the git directory.

### 2. Dependency Update

The new Python agents require additional libraries (`PyYAML`, `bcrypt`, `Flask-SocketIO`).

```bash
pip3 install -r requirements.txt
```

### 3. Cleanup Legacy Cron

Remove any old crontab entries that were manually triggering scripts like `auto-heal.sh` or `metrics.sh`. These are now handled by the persistent `run.sh` supervisor.

### 4. Initialize State

Run the new initialization script to scaffold the directory structure and provision the default admin user:

```bash
bash control-plane/init.sh
```

### 5. Launch the Supervisor

Start the new control plane:

```bash
bash control-plane/run.sh
```

---

## 🧱 Component Mapping (v1.1 vs v1.2)

| Legacy Component | Modern Agent | Purpose |
| :--- | :--- | :--- |
| `monitor.sh` | `monitor.py` | Container health sensing |
| `metrics.sh` | `metrics.py` | Telemetry & history |
| `auto-heal.sh` | `reconcile.py` | State enforcement |
| `api.py` | `server.py` | Dashboard & Web API |
| `ha-leader.sh` | `leader.py` | Cluster consensus |

---

## ⚠️ Important Note

**Configuration Volume**: Ensure your Docker containers are using the standardized `/mnt` mount point for persistent data. v1.2.0 agents enforce this mount for all monitored services to ensure portable storage.
