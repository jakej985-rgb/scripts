# Changelog

## v7.0.0 — Container Orchestration Platform

### v5.1 — Service Discovery (Auto-Detect Nodes)
- Node agent upgraded to heartbeat-based registration
- Nodes auto-register via POST to `/api/register`
- In-memory node registry with 30s auto-prune of stale heartbeats
- Static `nodes.json` kept as fallback, heartbeats override
- No more manual node configuration needed

### v5.2 — Job Scheduler (Cluster-Wide Tasks)
- New `scheduler-agent.sh` — cron-like schedule matching per-minute
- New `jobs.json` — declarative job definitions with cron schedules
- Supports `local`, hostname-specific, and `all` (cluster-wide) targeting
- Job cooldown prevents double-execution within same minute
- API endpoints: `/api/run_job/<job>`, `/api/execute/<job>`

### v6 — Container Auto-Placement
- `choose_best_node()` — scores nodes by CPU + MEM + container count
- `/api/deploy` — deploys container to best available node or specified target
- `/api/run_container` — starts container on local node
- `/api/node/metrics` — exposes CPU/MEM/container count per node

### v6.1 — Auto-Scaling Containers
- New `scaling-agent.sh` — CPU-based scale up/down logic
- New `scaling.json` — per-service min/max replicas and CPU thresholds
- 5-minute cooldown between scale events per service
- Lock file prevents concurrent scaling operations
- Only removes replica containers, never the original

### v6.2 — Rolling Updates (Zero Downtime)
- `/api/rolling_update/<name>` — pull latest, start new, verify, swap, remove old
- Automatic rollback if new container fails to start
- 5-second health verification before cutover
- Logged to actions.log

### v7 — Declarative System (Desired State)
- New `reconcile-agent.sh` — enforces desired state from `cluster.yml`
- New `cluster.yml` — defines services, images, replicas, and node affinity
- Reconciliation runs every minute: compares actual vs desired, scales accordingly
- 3-minute cooldown per service between reconcile actions
- Supports starting stopped replicas and creating new ones

### Dashboard
- New "Orchestration" tab with deploy form, rolling update, scaling/reconcile/scheduler logs
- Version bumped to v7 in UI header
- Cluster tab updated with "Auto-Discovery + Heartbeat" label
- Form input styling for deploy and update controls
- Sub-log renderer for scaling/reconcile/scheduler panels

### Pipeline
- Master controller (`m3tal.sh`) now runs 15 agents in 6 phases:
  1. Data Collection: monitor, metrics, node-agent
  2. Analysis: analyzer, anomaly, dependency
  3. Decision: decision-engine
  4. AI: ai-agent
  5. Orchestration: scheduler, scaling, reconcile
  6. Communication: telegram-agent

---

## v5.0.0 — Full Control Plane
- v3.1: Anomaly detection (CPU/MEM thresholds)
- v3.2: Container dependency graph
- v4: Dashboard container control buttons
- v4.1: Chart.js time-series metrics graphs
- v4.2: RBAC (admin/operator/viewer roles)
- v5: Multi-node cluster with remote control

## v3.0.0 — Agent-Based Architecture
- 5 agent pipeline, Flask dashboard, Telegram control, safe AI
- Replaced 16 legacy scripts

## v1.0.0
- Initial production release
