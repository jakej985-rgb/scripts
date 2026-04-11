#!/usr/bin/env python3
"""
M3TAL Healer Agent — Runtime Integrity Guardian
v1.0.0 — Self-healing drift correction with adaptive intervals.
"""

import os
import sys
import time
from pathlib import Path

from utils.paths import REPO_ROOT, STATE_DIR, CONTROL_PLANE
from utils.guards import wrap_agent
from utils.healing import (
    acquire_healer_lock, release_healer_lock, log_event, is_writable
)

# We import the agent logic from init.py to ensure parity, but we'll use a wrapper
# to enforce "runtime-safe" behavior.
sys.path.append(str(REPO_ROOT / "control-plane"))
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

        # Returns health status for adaptive interval logic
        return is_ready

    finally:
        release_healer_lock()

def adaptive_loop():
    """Main loop with adaptive intervals based on system health."""
    while True:
        try:
            is_healthy = run_healing_cycle()
            
            # Adaptive Timing: 15s if unhealthy, 120s if healthy
            interval = 120 if is_healthy else 15
            time.sleep(interval)
        except Exception as e:
            log_event("healer", f"FATAL ERROR in healer loop: {e}")
            time.sleep(30) # Wait before retry

if __name__ == "__main__":
    # We don't use wrap_agent here because healer has its own interval logic 
    # and needs to handle its own locking with init.py
    log_event("healer", "M3TAL Healer Agent Started.")
    adaptive_loop()
