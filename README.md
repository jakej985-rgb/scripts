# M3TAL Media Server v5

Agent-based Docker orchestration with anomaly detection, dependency awareness, full UI control, metrics graphs, RBAC, and multi-node cluster support.

## Architecture

```
┌──────────┐   ┌──────────┐   ┌───────────┐   ┌───────────┐
│ Monitor  │ → │ Analyzer │ → │ Decision  │ → │  Action   │
└──────────┘   └──────────┘   │  Engine   │   │  Agent    │
                              └───────────┘   └───────────┘
┌──────────┐   ┌──────────┐        ↑               ↑
│ Metrics  │ → │ Anomaly  │ ───────┘               │
└──────────┘   └──────────┘                   ┌─────┴──────┐
┌──────────┐        ↑                         │ Telegram   │
│ Depend.  │ ───────┘                         └────────────┘
└──────────┘
┌──────────┐                           ┌─────────────┐
│ AI Agent │ ── recommendations ──→    │  Dashboard   │
└──────────┘                           │  (v4 + v5)  │
┌──────────┐                           └─────────────┘
│  Backup  │ (isolated, daily cron)
└──────────┘
```

## Structure

```
docker/
├── m3tal.sh                  ← Master controller (cron)
├── connections.env.example   ← Config template
├── dependencies.conf         ← Container dependency map (v3.2)
├── nodes.json                ← Cluster node URLs (v5)
│
├── agents/
│   ├── monitor.sh            ← Collects container + disk state
│   ├── analyzer.sh           ← Detects unhealthy / crash loops
│   ├── metrics-agent.sh      ← Docker stats + time-series CSV (v3.1)
│   ├── anomaly-agent.sh      ← CPU/MEM threshold detection (v3.1)
│   ├── dependency-agent.sh   ← Checks upstream dependencies (v3.2)
│   ├── decision-engine.sh    ← Rules, retries, anomalies, deps → actions
│   ├── action-agent.sh       ← Executes restarts, sends alerts
│   ├── backup-agent.sh       ← Daily backup with rotation
│   ├── telegram-agent.sh     ← Approval system + remote commands (v2.2)
│   ├── ai-agent.sh           ← Safe read-only AI recommendations (v3)
│   └── node-agent.sh         ← Status broadcaster for cluster (v5)
│
├── dashboard/
│   ├── server.py             ← Flask API + RBAC + control endpoints
│   ├── users.json            ← Role-based user accounts (v4.2)
│   ├── static/
│   └── templates/
│       └── index.html        ← Full control plane dashboard
│
├── state/                    ← Runtime state (git-ignored)
│   ├── locks/ cooldowns/ retries/
│   ├── containers.txt  metrics.txt  analysis.txt
│   ├── anomalies.txt  dependency-issues.txt  actions.txt
│   └── metrics-history.csv
│
├── logs/                     ← Centralized action logs
├── media/                    ← Media stack compose
├── maintenance/              ← Maintenance stack + dashboard compose
└── tattoo/                   ← Tattoo app compose
```

## Quick Start

```bash
# 1. Configure
cp /docker/connections.env.example /docker/connections.env
nano /docker/connections.env

# 2. Set up RBAC (change default passwords!)
nano /docker/dashboard/users.json

# 3. Make executable
chmod +x /docker/m3tal.sh /docker/agents/*.sh

# 4. Add cron
crontab -e
# * * * * * /docker/m3tal.sh
# 0 3 * * * /docker/agents/backup-agent.sh

# 5. Launch dashboard
cd /docker/maintenance && docker compose up -d dashboard
```

Dashboard available at `http://your-server:8888`

## Dashboard Tabs

| Tab | What It Shows |
|-----|---------------|
| **📦 Overview** | Container status with Restart/Stop/Start buttons, analysis, actions queue, anomalies, dependencies, retry meters |
| **📊 Metrics** | Live CPU/MEM bars per container, Chart.js time-series graphs, disk usage |
| **🧠 Intelligence** | AI recommendations (Ollama or local heuristics) |
| **📜 Logs** | Last 50 action history entries |
| **🌐 Cluster** | Multi-node status with online/offline detection |

## Safety Matrix

| Layer | Protection |
|---|---|
| Lock Files | Prevents overlapping agent runs |
| Cooldowns | 120s minimum between actions |
| Retry Limits | Max 3 auto-restarts per container |
| AI Boundaries | Read-only, never acts directly |
| Telegram Gate | Critical actions require yes/no approval |
| RBAC | admin/operator/viewer role hierarchy |
| POST-only | Control actions require POST (no accidental GETs) |

## Telegram Commands

| Command | Action |
|---|---|
| `status` | Container overview |
| `yes` / `no` | Approve or reject pending action |
| `/restart [name]` | Restart container |
| `/logs [name]` | Tail 30 lines |
| `/help` | List commands |

## Cluster Setup (v5)

1. On each remote node, run `node-agent.sh`
2. Edit `/docker/nodes.json` with node URLs
3. Dashboard aggregates all nodes in the Cluster tab
4. Remote restart available via `/api/cluster/restart/<node>/<container>`
