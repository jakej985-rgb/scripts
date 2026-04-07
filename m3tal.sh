#!/bin/bash

# ⚡ M3TAL v7 — Master Controller
# Runs the full agent pipeline in order
# Cron: * * * * * /docker/m3tal.sh

BASE="/docker/agents"

source /docker/connections.env 2>/dev/null

# Phase 1: Data collection
bash $BASE/monitor.sh
bash $BASE/metrics-agent.sh
bash $BASE/node-agent.sh

# Phase 2: Analysis
bash $BASE/analyzer.sh
bash $BASE/anomaly-agent.sh
bash $BASE/dependency-agent.sh

# Phase 3: Decision + action
bash $BASE/decision-engine.sh

# Phase 4: AI analysis (safe, read-only)
bash $BASE/ai-agent.sh

# Phase 5: Orchestration
bash $BASE/scheduler.sh
bash $BASE/scaling-agent.sh
bash $BASE/reconcile.sh

# Phase 6: Process Telegram commands
bash $BASE/telegram-agent.sh
