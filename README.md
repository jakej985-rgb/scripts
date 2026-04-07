# 🚀 M3TAL Control Plane

A lightweight, agent-based container orchestration system for homelabs and small-scale infrastructure.

![Status](https://img.shields.io/badge/status-active-success) ![License](https://img.shields.io/badge/license-MIT-blue)

---

## ⚙️ Features

* 🧠 Agent-based automation (safe + controlled)
* 📊 Metrics + anomaly detection
* 🔄 Auto-scaling containers
* 🚀 Rolling updates (zero downtime ready)
* 🌐 Multi-node cluster support
* 📦 Declarative service management (`cluster.yml`)
* 🖥 Web dashboard (RBAC secured)
* 📲 Telegram approval system

---

## 🧱 Architecture

```
agents/     → system logic (monitor, decision, scaling)
dashboard/  → UI + API control plane
config/     → declarative configs
state/      → runtime + logs
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/jakej985-rgb/M3tal-Control-Plane.git
cd M3tal-Control-Plane

chmod +x install.sh
./install.sh
```

Access dashboard:

```
http://YOUR_SERVER_IP:8888
```

---

## 🔐 Security Model

* Role-based access control (admin/operator/viewer)
* Action approval system (Telegram optional)
* No destructive automation by default

---

## 📦 Example Declarative Config

```yaml
services:
  radarr:
    image: lscr.io/linuxserver/radarr
    replicas: 2

  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent
    replicas: 1
```

---

## ⚠️ Disclaimer

This is **not Kubernetes** — it’s a controlled, lightweight alternative designed for:

* homelabs
* single / few-node clusters
* learning orchestration concepts

---

## 🧠 Philosophy

> Control > Automation
> Stability > Complexity
> Observability > Guessing

---

## 📈 Roadmap

* UI improvements (React dashboard)
* service mesh / routing
* auto-scaling improvements
* cluster scheduling policies

---

## 🤝 Contributing

PRs welcome — keep it clean, safe, and modular.

---

## 📜 License

MIT
