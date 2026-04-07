# M3TAL Media Server v7

Lightweight container orchestration platform with auto-scaling, declarative state, rolling updates, service discovery, and full UI control.

## Architecture

```
┌───────────────── DATA COLLECTION ──────────────────┐
│  Monitor  →  Metrics  →  Node Agent (heartbeat)    │
└────────────────────────┬───────────────────────────┘
                         ▼
┌───────────────── ANALYSIS ─────────────────────────┐
│  Analyzer  →  Anomaly Detection  →  Dependencies   │
└────────────────────────┬───────────────────────────┘
                         ▼
┌───────────────── DECISION ─────────────────────────┐
│              Decision Engine                        │
│  (retries, anomalies, deps, AI recommendations)    │
└────────────────────────┬───────────────────────────┘
                         ▼
┌───────────────── ORCHESTRATION ────────────────────┐
│  Scheduler  →  Scaling Agent  →  Reconcile Agent   │
│  Action Agent ← Telegram Approval                  │
└────────────────────────┬───────────────────────────┘
                         ▼
┌───────────────── INTERFACE ────────────────────────┐
│  Dashboard (6 tabs) ← API ← Telegram Bot          │
└────────────────────────────────────────────────────┘
```

## 15 Agents Pipeline

| # | Agent | Phase | Role |
|---|-------|-------|------|
| 1 | `monitor.sh` | Data | Container + disk state |
| 2 | `metrics-agent.sh` | Data | Docker stats + time-series CSV |
| 3 | `node-agent.sh` | Data | Heartbeat + status broadcast |
| 4 | `analyzer.sh` | Analysis | Unhealthy / crash loop detection |
| 5 | `anomaly-agent.sh` | Analysis | CPU/MEM threshold alerts |
| 6 | `dependency-agent.sh` | Analysis | Upstream dependency checks |
| 7 | `decision-engine.sh` | Decision | Rules → action queue |
| 8 | `ai-agent.sh` | AI | Safe read-only recommendations |
| 9 | `scheduler-agent.sh` | Orchestration | Cron-like cluster job execution |
| 10 | `scaling-agent.sh` | Orchestration | Auto-scale by CPU load |
| 11 | `reconcile-agent.sh` | Orchestration | Enforce desired state from cluster.yml |
| 12 | `action-agent.sh` | Execution | Restarts + Telegram alerts |
| 13 | `backup-agent.sh` | Execution | Daily backup rotation |
| 14 | `telegram-agent.sh` | Communication | Remote commands + approvals |
| 15 | `node-agent.sh` | Cluster | Status broadcaster |

## Dashboard Tabs

| Tab | Features |
|-----|----------|
| **📦 Overview** | Container status + control buttons, analysis, actions, anomalies, dependencies, retries |
| **📊 Metrics** | Live CPU/MEM bars, Chart.js time-series, disk usage |
| **🧠 Intelligence** | AI recommendations (Ollama / heuristic) |
| **📜 Logs** | Last 50 action history entries |
| **⚙️ Orchestration** | Deploy container, rolling update, scaling/reconcile/scheduler logs |
| **🌐 Cluster** | Auto-discovered nodes, online/offline status |

## Quick Start

```bash
# 1. Configure
cp /docker/connections.env.example /docker/connections.env
nano /docker/connections.env

# 2. RBAC (change defaults!)
cp /docker/dashboard/users.json.example /docker/dashboard/users.json
nano /docker/dashboard/users.json

# 3. Make executable
chmod +x /docker/m3tal.sh /docker/agents/*.sh

# 4. Install dependencies (host)
apt install jq
# yq: https://github.com/mikefarah/yq (for reconcile-agent)

# 5. Cron
crontab -e
# * * * * * /docker/m3tal.sh
# 0 3 * * * /docker/agents/backup-agent.sh

# 6. Dashboard
cd /docker/maintenance && docker compose up -d dashboard
```

Dashboard: `http://your-server:8888`

## Config Files

| File | Purpose |
|------|---------|
| `connections.env` | Secrets + thresholds + cluster config |
| `dependencies.conf` | Container dependency map |
| `jobs.json` | Scheduled job definitions |
| `scaling.json` (state/) | Auto-scaling rules per service |
| `cluster.yml` | Desired state declaration |
| `nodes.json` | Static node fallback (heartbeats override) |
| `users.json` (dashboard/) | RBAC accounts |

## Safety Matrix

| Layer | Protection |
|---|---|
| Lock Files | Prevents overlapping agent runs |
| Cooldowns | 120s actions, 300s scaling, 180s reconcile, 60s scheduler |
| Retry Limits | Max 3 auto-restarts per container |
| AI Boundaries | Read-only, never acts directly |
| Telegram Gate | Critical actions require yes/no approval |
| RBAC | admin/operator/viewer role hierarchy |
| POST-only | Control actions require POST requests |
| Rollback | Rolling updates auto-revert on failure |
| Replica Safety | Reconcile never removes original containers |
