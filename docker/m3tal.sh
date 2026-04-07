#!/bin/bash

# ⚡ M3TAL v2 — Master Controller
# Runs the full agent pipeline in order
# Cron: * * * * * /docker/m3tal.sh

BASE="/docker"
AGENTS="$BASE/agents"

source $BASE/connections.env 2>/dev/null

# Phase 1-3: Core pipeline
bash $AGENTS/monitor.sh
bash $AGENTS/analyzer.sh
bash $AGENTS/decision-engine.sh

# Phase 4: AI analysis (safe, read-only)
bash $AGENTS/ai-agent.sh

# Phase 5: Process Telegram commands
bash $AGENTS/telegram-agent.sh
