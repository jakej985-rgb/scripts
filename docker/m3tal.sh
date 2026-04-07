#!/bin/bash

# ⚡ M3TAL v7 — Master Controller
# Runs the full agent pipeline in order
# Cron: * * * * * /docker/m3tal.sh

BASE="/docker"
AGENTS="$BASE/agents"

source $BASE/connections.env 2>/dev/null

# Phase 1: Data collection
bash $AGENTS/monitor.sh
bash $AGENTS/metrics-agent.sh
bash $AGENTS/node-agent.sh

# Phase 2: Analysis
bash $AGENTS/analyzer.sh
bash $AGENTS/anomaly-agent.sh
bash $AGENTS/dependency-agent.sh

# Phase 3: Decision + action
bash $AGENTS/decision-engine.sh

# Phase 4: AI analysis (safe, read-only)
bash $AGENTS/ai-agent.sh

# Phase 5: Orchestration
bash $AGENTS/scheduler-agent.sh
bash $AGENTS/scaling-agent.sh
bash $AGENTS/reconcile-agent.sh

# Phase 6: Process Telegram commands
bash $AGENTS/telegram-agent.sh
