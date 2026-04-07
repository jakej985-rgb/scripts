#!/bin/bash

# 🤖 AI Agent v3 — Safe + Bounded
# Reads action logs, generates conservative recommendations
# NEVER acts directly — output is read-only

LOGS="/docker/logs/actions.log"
OUT="/docker/state/ai-recommendations.txt"

# Only run if AI is enabled
source /docker/connections.env 2>/dev/null
if [ "$ENABLE_AI" != "true" ]; then
  exit 0
fi

# Grab recent log activity
TAIL=$(tail -n 50 "$LOGS" 2>/dev/null)

if [ -z "$TAIL" ]; then
  echo "No recent actions to analyze." > $OUT
  exit 0
fi

PROMPT="You are a conservative systems administrator AI for a Docker media server.

Analyze these recent action logs and suggest safe actions.

RULES (STRICT):
- NEVER suggest rebooting the system
- NEVER suggest deleting data or volumes
- NEVER suggest automatic rollbacks
- Prefer alerts over restarts
- Be conservative — when in doubt, suggest monitoring
- Keep suggestions short and actionable

LOGS:
$TAIL

Respond with a numbered list of recommendations."

# Try Ollama (local) first
if [ -n "$OLLAMA_HOST" ]; then
  RESPONSE=$(curl -s --max-time 30 "$OLLAMA_HOST/api/generate" \
    -d "{\"model\":\"llama3\",\"prompt\":\"$PROMPT\",\"stream\":false}" 2>/dev/null)
  
  ANSWER=$(echo "$RESPONSE" | jq -r '.response // empty' 2>/dev/null)
  
  if [ -n "$ANSWER" ]; then
    echo "$(date '+%F %T') — Ollama (local)" > $OUT
    echo "---" >> $OUT
    echo "$ANSWER" >> $OUT
    exit 0
  fi
fi

# Fallback: simple heuristic analysis (no external API needed)
echo "$(date '+%F %T') — Heuristic Analysis (local fallback)" > $OUT
echo "---" >> $OUT

RESTART_COUNT=$(grep -c "Restarted" <<< "$TAIL" 2>/dev/null || echo 0)
ALERT_COUNT=$(grep -c "ALERT" <<< "$TAIL" 2>/dev/null || echo 0)
FREQUENT=$(grep "Restarted" <<< "$TAIL" | awk '{print $NF}' | sort | uniq -c | sort -rn | head -3)

if [ "$RESTART_COUNT" -gt 5 ]; then
  echo "1. ⚠️ High restart count ($RESTART_COUNT). Check for crash loops." >> $OUT
fi

if [ "$ALERT_COUNT" -gt 3 ]; then
  echo "2. ⚠️ Multiple alerts detected ($ALERT_COUNT). Review container health." >> $OUT
fi

if [ -n "$FREQUENT" ]; then
  echo "3. 🔁 Most restarted containers:" >> $OUT
  echo "$FREQUENT" >> $OUT
fi

if [ "$RESTART_COUNT" -eq 0 ] && [ "$ALERT_COUNT" -eq 0 ]; then
  echo "✅ System looks stable. No action needed." >> $OUT
fi
