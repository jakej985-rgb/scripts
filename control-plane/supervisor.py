#!/usr/bin/env python3
"""
M3TAL Supervisor — Reliable, Cross-Platform Agent Process Manager
v1.3.0 — Python replacement for run.sh

Launches all autonomous agents as child processes with:
  - Exponential backoff on crash (max 60s)
  - Docker socket liveness check before launch
  - SIGTERM / SIGINT graceful shutdown
  - Per-agent log routing
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

# --- Agent Registry -----------------------------------------------------------
# (name, script_path_relative_to_AGENTS_DIR, is_leader_tier)
AGENTS = [
    # Tier 0 — Leader election (runs first, others wait)
    ("leader",    "leader.py",       True),
    # Tier 1 — Core pipeline
    ("registry",  "registry.py",     False),
    ("monitor",   "monitor.py",      False),
    ("metrics",   "metrics.py",      False),
    ("scaling",   "scaling.py",      False),
    ("anomaly",   "anomaly.py",      False),
    ("decision",  "decision.py",     False),
    ("reconcile", "reconcile.py",    False),
    # Tier 2 — Maintenance / health (runs on all nodes)
    ("scorer",    "health_score.py", False),
    ("observer",  "observer.py",     False),
    # ("chaos",   "chaos_test.py",   False),  # Intentionally disabled in prod
]

# --- Globals ------------------------------------------------------------------
_shutdown_event = threading.Event()
_children: list[subprocess.Popen] = []
_children_lock = threading.Lock()


def _register_child(proc: subprocess.Popen) -> None:
    with _children_lock:
        _children.append(proc)


def _unregister_child(proc: subprocess.Popen) -> None:
    with _children_lock:
        if proc in _children:
            _children.remove(proc)


def _handle_signal(signum, _frame):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Supervisor received signal {signum}. Shutting down...")
    _shutdown_event.set()
    with _children_lock:
        children = list(_children)
    for proc in children:
        try:
            proc.terminate()
        except OSError:
            pass


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


# --- Agent Runner -------------------------------------------------------------

def run_agent(name: str, script: str) -> None:
    """Run a single agent in a supervised loop with exponential backoff."""
    crash_count = 0
    log_path = LOG_DIR / f"{name}.log"

    while not _shutdown_event.is_set():
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] Starting {name}...")

        try:
            with open(log_path, "a", encoding="utf-8") as log_file:
                proc = subprocess.Popen(
                    [PYTHON, str(AGENTS_DIR / script)],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
                _register_child(proc)
                try:
                    exit_code = proc.wait()  # Agents are persistent — no timeout
                finally:
                    _unregister_child(proc)
        except Exception as e:
            exit_code = 1
            ts2 = time.strftime("%H:%M:%S")
            print(f"[{ts2}] ERROR: {name}: {e}")

        if _shutdown_event.is_set():
            break

        if exit_code == 0:
            crash_count = 0
            time.sleep(5)  # Agent exited cleanly, restart after brief pause
        else:
            crash_count += 1
            wait_time = min(5 * crash_count, 60)
            ts2 = time.strftime("%H:%M:%S")
            print(f"[{ts2}] CRASH: {name} (exit {exit_code}). Backoff {wait_time}s...")
            time.sleep(wait_time)


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
    print(f"[{ts}] Supervisor launching agents...")

    # 2. Launch leader first, wait for election to settle
    threads: list[threading.Thread] = []

    for name, script, is_leader in AGENTS:
        # Audit fix 2.6: Do not use daemon threads. Join them on shutdown.
        t = threading.Thread(target=run_agent, args=(name, script), daemon=False, name=f"agent-{name}")
        threads.append(t)
        t.start()

        if is_leader:
            time.sleep(2)  # Wait for leader election

    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] All agents running.")

    # 3. Wait for shutdown signal
    try:
        while not _shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown_event.set()

    # 4. Join all agent threads (Audit fix 2.6)
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Waiting for agent threads to exit...")
    for t in threads:
        t.join(timeout=5)

    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Supervisor shutdown complete.")


if __name__ == "__main__":
    main()
