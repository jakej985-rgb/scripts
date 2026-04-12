#!/bin/bash
# --- M3TAL Linux Log Collector ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( dirname "$( dirname "$SCRIPT_DIR" )" )"
cd "$REPO_ROOT"

# Ensure venv exists or use system python
if [ -d "venv" ]; then
    ./venv/bin/python scripts/debug/collect_linux_debug_log.py
else
    python3 scripts/debug/collect_linux_debug_log.py
fi

echo ""
echo "Debug collection complete."
echo "Files generated in REPO_ROOT:"
echo " - logs_linux.txt"
echo " - error_log_linux.txt"
chmod +x scripts/debug/collect_linux.sh 2>/dev/null || true
