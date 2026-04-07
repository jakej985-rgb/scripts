# Changelog

## v5.0.0 — Full Control Plane

### v3.1 — Anomaly Detection (Metrics-Based)
- New `metrics-agent.sh` — captures docker stats (CPU%, MEM) per container
- New `anomaly-agent.sh` — flags containers exceeding CPU/MEM thresholds
- Metrics history stored as CSV time-series for graphing
- Auto-trims history to last 10,000 data points
- Decision engine processes `HIGH_CPU` and `HIGH_MEM` anomalies
- Action agent sends Telegram alerts for anomalies

### v3.2 — Container Dependency Graph
- New `dependency-agent.sh` — checks container-to-container and container-to-path relationships
- New `dependencies.conf` — declarative dependency map (radarr→qbittorrent, tdarr→/mnt/disk1, etc.)
- Decision engine processes `DEPENDENCY_DOWN` and `DEPENDENCY_MISSING` events
- Action agent sends context-aware alerts ("Radarr degraded because qbittorrent is down")

### v4 — Full UI Control Panel
- Container control buttons: Restart, Stop, Start (per container)
- "Approve Pending" button — executes force-mode on action-agent from browser
- All control actions are POST-protected (no accidental GET triggers)
- Action logging for all dashboard-initiated actions
- Toast notifications for action feedback

### v4.1 — Metrics Graphs (Time-Series)
- Chart.js integration with dual-axis CPU/MEM line charts
- `/api/metrics/<name>` endpoint returns last 100 data points
- Container selector dropdown auto-populated from history
- Responsive chart with JetBrains Mono axis labels

### v4.2 — Role-Based Access Control
- `users.json` — admin/operator/viewer roles
- Role hierarchy: admin (full) > operator (restart/stop/start) > viewer (read-only)
- HTTP Basic Auth on all endpoints
- Approve action restricted to admin role only

### v5 — Multi-Node Cluster
- `nodes.json` — maps node names to URLs
- `node-agent.sh` — lightweight status broadcaster for remote nodes
- `/api/cluster` — aggregates status from all nodes
- `/api/cluster/restart/<node>/<container>` — remote container restart
- Cluster tab in dashboard with per-node status view
- Offline detection with timeout handling

### Infrastructure
- Dashboard port moved to 8888 (avoids gluetun conflict on 8080)
- Docker socket mounted for dashboard container control
- `requests` library added to dashboard container
- Tabbed dashboard navigation (Overview, Metrics, Intelligence, Logs, Cluster)
- Master controller pipeline expanded with metrics, anomaly, and dependency agents

---

## v3.0.0 — Agent-Based Architecture
- Core: 5 agent pipeline (monitor → analyzer → decision-engine → action-agent + backup-agent)
- v2.1: Flask dashboard with live-polling glassmorphic UI
- v2.2: Telegram approval system (yes/no gate, /restart, /logs, /status)
- v3: Safe AI agent (Ollama + heuristic fallback, read-only recommendations)
- Safety: lock files, 120s cooldowns, 3-retry limits, force-mode via approval only
- Removed: 16 legacy scripts, stale api.py, lib/ directory

## v1.0.0
- Initial production release
- One-command installer
- Auto backup + retention
- Self-healing containers
- Telegram control + alerts
