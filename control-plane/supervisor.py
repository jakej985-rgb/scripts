#!/usr/bin/env python3
"""
M3TAL Supervisor — Infrastructure & Docker Orchestrator
v1.4.0 — Decoupled Bootstrap

Validates environment, ensures Docker liveness, executes system initialization
(init.py), and then hands off control to the autonomous Agent Runner.
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

# --- Context Anchoring --------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent

# Add support directories to system path
for path in [REPO_ROOT / "scripts", REPO_ROOT / "dashboard"]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

try:
    from validate_env import validate_env, load_env
    from validate_images import validate_images
    from progress_utils import Spinner
except ImportError:
    validate_env = None
    validate_images = None
    Spinner = None

# --- Path System --------------------------------------------------------------
STATE_DIR = BASE_DIR / "state"
LOG_DIR = STATE_DIR / "logs"
AGENTS_DIR = BASE_DIR / "agents"
DOCKER_DIR = REPO_ROOT / "docker" / "media"

PYTHON = sys.executable  # Use the same interpreter that launched us

# --- Globals ------------------------------------------------------------------
_shutdown_event = threading.Event()

def _handle_signal(signum, _frame):
    ts = time.strftime("%H:%M:%S")
    print(f"\n[{ts}] Supervisor received signal {signum}. Shutting down...")
    _shutdown_event.set()

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# --- Docker Liveness ---------------------------------------------------------

def wait_for_docker(max_retries: int = 30, interval: float = 4.0) -> bool:
    """Block until the Docker socket is responsive or timeout."""
    spinner = Spinner("Waiting for Docker socket")
    if spinner: spinner.start()
    
    use_shell = os.name == "nt"  # Windows often needs shell=True for docker shims
    
    for attempt in range(1, max_retries + 1):
        if spinner:
            spinner.set_message(f"Waiting for Docker socket (Attempt {attempt}/{max_retries})")
            
        try:
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                timeout=10,
                shell=use_shell
            )
            if result.returncode == 0:
                if spinner: spinner.stop(success=True, final_msg="Docker is ready")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        if _shutdown_event.is_set():
            if spinner: spinner.stop(success=False)
            return False
        time.sleep(interval)

    if spinner: spinner.stop(success=False, final_msg="Docker not found after 2 minutes")
    return False




# --- Main Entry ---------------------------------------------------------------

def main() -> None:
    # 0. Context Guard
    if load_env:
        load_env()
    os.environ["INIT_ALREADY_RUN"] = "0"

    # 1. Docker liveness
    if not wait_for_docker():
        sys.exit(1)

    # 2. Run Self-Healing Orchestrator (init.py)
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Launching orchestrator (init.py)...")
    
    init_args = [PYTHON, "init.py"]
    
    # Pass repair flags if requested
    if "--pull-images" in sys.argv:
        init_args.extend(["--pull", "--fix"])
        
    try:
        # Rex Fix Plan: Enforce correct context (cwd + env)
        subprocess.run(
            init_args, 
            cwd=str(BASE_DIR), 
            env=os.environ.copy(), 
            check=True
        )
    except subprocess.CalledProcessError:
        print("[FATAL] Orchestration failed. System not healthy for startup.")
        sys.exit(1)

    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Supervisor validation and orchestration complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
