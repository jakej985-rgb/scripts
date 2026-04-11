#!/usr/bin/env python3
"""
M3TAL Supervisor — Infrastructure Orchestrator
v1.5.0 — Premium UI & Autonomous Handoff
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# --- Context Anchoring --------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from progress_utils import (
    Header, Heartbeat, Spinner,
    CYAN, GREEN, YELLOW, RED, BOLD, END, DIM
)

# --- Configuration ------------------------------------------------------------
PYTHON = sys.executable
HB = Heartbeat()
_shutdown_event = threading.Event()

def _handle_signal(signum, _frame):
    HB.log(f"Supervisor received signal {signum}. Shutting down...", symbol="⚠")
    _shutdown_event.set()

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# --- Logic --------------------------------------------------------------------

def wait_for_docker(max_retries: int = 30, interval: float = 4.0) -> bool:
    """Block until the Docker socket is responsive."""
    HB.ping("Detecting Docker socket")
    s = Spinner("Detecting Docker socket")
    s.start()
    
    use_shell = os.name == "nt"
    
    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(["docker", "ps"], capture_output=True, timeout=10, shell=use_shell)
            if result.returncode == 0:
                s.stop(success=True, final_msg="Docker engine responsive")
                return True
        except:
            pass
            
        if _shutdown_event.is_set():
            s.stop(success=False, final_msg="Detection cancelled")
            return False
            
        s.set_message(f"Waiting for Docker socket (Attempt {attempt}/{max_retries})")
        time.sleep(interval)

    s.stop(success=False, final_msg="Docker timeout")
    return False

def main() -> None:
    Header.show("M3TAL Infrastructure Supervisor", "Autonomous Control Plane Entry")
    
    HB.start()
    
    # 1. Docker check
    if not wait_for_docker():
        print(f"\n{RED}{BOLD}FATAL: Docker not found. Is the Docker Desktop running?{END}")
        sys.exit(1)

    # 2. Run Self-Healing Orchestrator (init.py)
    HB.ping("Launching init.py")
    HB.log("Handoff to Self-Healing Orchestrator (init.py)...")
    
    try:
        # Pause HB for init's own UI
        HB.stop()
        
        # Import and run directly to preserve terminal context (Live UI)
        import init
        repair_scope = None
        for arg in sys.argv:
             if arg.startswith("--repair="): repair_scope = arg.split("=")[1]
             elif arg == "--repair": repair_scope = "all"
        
        success = init.run_init(repair_scope=repair_scope)
        if not success:
            raise RuntimeError("Initialization failed")
        
        # Resume HB for final message
        HB.start()
        HB.ping("Finalizing handoff")
        HB.log("Orchestration complete. System is stable.", symbol="★")
        
    except Exception as e:
        print(f"\n{RED}{BOLD}FATAL: Orchestration failed: {e}{END}")
        sys.exit(1)

    finally:
        HB.stop()
    
    print(f"\n{GREEN}{BOLD}[SUCCESS] Supervisor validation complete.{END}\n")

if __name__ == "__main__":
    main()
