# 🚀 M3TAL Control Plane (v1.2.0)

> A lightweight, autonomous, and self-healing container orchestration system for homelabs and small-scale clusters.

![Status](https://img.shields.io/badge/status-active-success) ![License](https://img.shields.io/badge/license-MIT-blue) ![Version](https://img.shields.io/badge/version-1.2.0-orange)

M3TAL (Modern Media Management & Management) is an "Autonomous Local Cloud" that manages your Docker containers so you don't have to. It detects failures, scales services, and ensures your media stack is always online.

---

## 🔥 Key Features

* **🧠 Autonomous Self-Healing**: Detects crashed containers and restarts them automatically within seconds.
* **🌏 Distributed Leadership**: High Availability (HA) support — switch between nodes automatically if the master fails.
* **📈 Deep Metrics**: Real-time monitoring of CPU, Memory, and I/O for both the system and every individual container.
* **🔄 Auto-Scaling**: Automatically adjusts service replicas based on load (Upscale on high CPU, Downscale on idle).
* **🛡️ Hardened Security**: Token-based RBAC, BCrypt password hashing, and shell-injection protection.
* **🖥️ Web Dashboard**: Simple UI to manage your cluster, view metrics history, and approve AI actions.
* **🚑 Disaster Recovery**: Built-in `backup.sh` and `restore.sh` scripts for one-click stack recovery.

---

## 🚀 Quick Start

For a detailed beginner guide, see [Getting Started](docs/GET_STARTED.md).

### 1. Install

```bash
git clone https://github.com/jakej985-rgb/M3tal-Media-Server.git
cd M3tal-Media-Server

# Recommended: Create a virtual environment
python3 -m venv venv
# On Windows (PowerShell), you may need to run this first:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Cross-platform installer (recommended)
python3 install.py

# Or on Linux/macOS only:
# bash install.sh
```

### 2. Login

Open your browser to `http://YOUR_SERVER_IP:8080`.

* **Username**: `admin`
* **Password**: the admin password you chose during the interactive setup
* *⚠️ If you need to rotate or recover the admin password later, run `python scripts/config/manage_users.py --reset-admin`.*

---

## 🧱 Architecture

The system uses a "Sense-Think-Act" loop driven by independent Python agents:

1. **Registry** → Discovers your Docker stacks.
2. **Monitor** → Senses container health.
3. **Metrics** → Gathers performance data.
4. **Anomaly** → Identifies issues (crashes, leaks).
5. **Decision** → Plans recovery or scaling actions.
6. **Reconcile** → Executes actions (restart/scale).

---

## 🔐 Security & Safety

M3TAL is designed to be **safe**:

* **No Direct Calls**: Agents communicate only via atomic JSON state files.
* **Cooldowns**: Prevents "flapping" or restart loops by enforcing wait times between actions.
* **Allowlisting**: Only approved images and container names are permitted via the API.

---

## 🗺 Roadmap

* [ ] React-based "Admin Center" UI
* [ ] Predictive AI Scaling (predicting load spikes)
* [ ] Gossip protocol node discovery
* [ ] Plugin system for custom agents

---

## 📜 License & Support

Licensed under MIT.

If you like this project, give it a star ⭐!
