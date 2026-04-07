# Changelog

## v2.0.0 — Agent-Based Architecture

**Breaking:** Full rewrite from chaotic scripts to controlled agent pipeline.

### Core (v2.0)
- Replaced all maintenance scripts with 5 core agents
- `m3tal.sh` master controller runs pipeline via cron
- Lock files prevent overlapping agent runs
- Cooldowns (120s) prevent action spam
- Per-container retry limits (max 3 auto-restarts)
- Removed: auto-reboot, auto-rollback, predictive-ai actions

### Dashboard (v2.1)
- Flask-based web dashboard at port 8080
- Live-polling JSON API (`/api/state`)
- Real-time container status, analysis, actions queue
- Retry tracking meters per container
- Disk usage view
- Action history log (last 50 entries)
- AI recommendations panel

### Telegram Control (v2.2)
- `telegram-agent.sh` handles approval flow
- `yes` / `no` to approve or reject pending actions
- `status` for container overview
- `/restart [name]` for manual restarts
- `/logs [name]` to tail container logs
- `/help` for command reference
- Chat ID security — only authorized users

### AI Layer (v3)
- `ai-agent.sh` — read-only AI analysis
- Tries Ollama (local LLM) first
- Falls back to local heuristic analysis
- Outputs to `state/ai-recommendations.txt`
- Decision engine reads suggestions but NEVER auto-executes
- AI restart suggestions require human approval
- Controlled via `ENABLE_AI=true/false` in connections.env

### Removed
- `api.py` (replaced by dashboard)
- `auto-heal.sh` (replaced by monitor + decision engine)
- `auto-fix.sh`
- `auto-reboot-if-unhealthy.sh`
- `auto-rollback-on-update.sh`
- `predictive-ai.sh` (replaced by ai-agent.sh)
- `ai-log-analyzer.sh`
- `log-watcher.sh`
- `graceful-reboot.sh`
- `safe-reboot.sh`
- `learning-mode.sh`
- `manage-cron.sh`
- `maintenance-mode.sh`
- `post-reboot-check.sh`
- `install.sh`
- `lib/` directory

## v1.0.0
- Initial production release
- One-command installer (install.sh)
- Auto backup + retention
- Self-healing containers
- Telegram control + alerts
- AI-style log summaries
- Auto rollback system
- Monitoring stack (Grafana + Prometheus + Node Exporter)
- Secure env-based configuration
- Root-level simplified structure
