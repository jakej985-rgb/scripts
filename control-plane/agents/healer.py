#!/usr/bin/env python3
"""
M3TAL Healer Agent — Runtime Integrity Guardian
v1.0.0 — Self-healing drift correction with adaptive intervals.
"""

import os
import sys
import time
from pathlib import Path

# --- Path System Bootstrap ----------------------------------------------------
# healer.py (v1.1.0) — Path stability fix
from pathlib import Path
import sys

AGENTS_DIR = Path(__file__).resolve().parent
if str(AGENTS_DIR) not in sys.path:
    sys.path.append(str(AGENTS_DIR))

from utils.paths import REPO_ROOT, STATE_DIR, CONTROL_PLANE
from utils.guards import wrap_agent
from utils.healing import (
    acquire_healer_lock, release_healer_lock, log_event, is_writable
)

# Use absolute path from paths.py for init import
if str(CONTROL_PLANE) not in sys.path:
    sys.path.append(str(CONTROL_PLANE))
import init

MAX_CYCLE_TIME = 15  # seconds

def run_healing_cycle():
    """Performs a lightweight sanity check and repair of the system."""
    if os.getenv("M3TAL_HEALER_DISABLED"):
        log_event("healer", "Healer is disabled via environment variable.")
        return

    start_time = time.time()
    init.MODE = "runtime" # Enforce runtime context

    if not acquire_healer_lock():
        # init.py or another healer is running
        return

    try:
        log_event("healer", "--- Runtime Healing Cycle Started ---")
        
        # 1. FS Check (Lightweight)
        init.fs_agent(repair_mode=False) 
        
        # 2. Log Re-scaffolding
        init.log_agent(repair_mode=False)
        
        # 3. State Validation (Atomic)
        init.state_agent(repair_mode=False)
        
        # 4. Docker Health Audit (No restarts in runtime mode)
        init.docker_agent(repair_mode=False)
        
        # 5. Final Health Update
        is_ready = init.health_agent()
        
        duration = time.time() - start_time
        log_event("healer", f"--- Cycle Complete ({duration:.2f}s) Ready={is_ready} ---")
        
        if duration > MAX_CYCLE_TIME:
            log_event("healer", f"WARNING: Healing cycle took {duration:.2f}s (Limit {MAX_CYCLE_TIME}s)")

        # Adaptive Timing: wrap_agent uses interval=15. 
        # If healthy, we sleep an extra 105s here to reach 120s total interval.
        if is_ready:
            time.sleep(105)

    finally:
        release_healer_lock()

if __name__ == "__main__":
    log_event("healer", "M3TAL Healer Agent Started.")
    wrap_agent("healer", run_healing_cycle, interval=15)
