#!/bin/bash
# M3TAL Blackout — Unified Shutdown Command
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi
$PYTHON_CMD scripts/maintenance/shutdown.py
