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

import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "scripts"))
try:
    from validate_env import validate_env
except ImportError:
    validate_env = None

BASE_DIR = REPO_ROOT / "control-plane"
AGENTS_DIR = BASE_DIR / "agents"
STATE_DIR = BASE_DIR / "state"
LOG_DIR = STATE_DIR / "logs"

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
    print("[CHECK] Waiting for Docker socket...")
    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print("[CHECK] Docker is ready.")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        if _shutdown_event.is_set():
            return False
        time.sleep(interval)

    print("[FATAL] Docker not found after 2 minutes. Exiting.")
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
            with open(log_path, "a") as log_file:
                proc = subprocess.Popen(
                    [PYTHON, str(AGENTS_DIR / script)],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
                _register_child(proc)
                try:
                    exit_code = proc.wait(timeout=300)  # 5-minute safety timeout per cycle
                finally:
                    _unregister_child(proc)
        except subprocess.TimeoutExpired:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            exit_code = 1
            ts2 = time.strftime("%H:%M:%S")
            print(f"[{ts2}] TIMEOUT: {name}. Forcing restart...")
        except Exception as e:
            exit_code = 1
            ts2 = time.strftime("%H:%M:%S")
            print(f"[{ts2}] ERROR: {name}: {e}")

        if _shutdown_event.is_set():
            break

        if exit_code == 0:
            crash_count = 0
            time.sleep(5)  # Main loop interval
        else:
            crash_count += 1
            wait_time = min(5 * crash_count, 60)
            ts2 = time.strftime("%H:%M:%S")
            print(f"[{ts2}] CRASH: {name}. Backoff {wait_time}s...")
            time.sleep(wait_time)


# --- Main Entry ---------------------------------------------------------------

def main() -> None:
    # 0. Rex Guardrail: Check environment integrity
    if validate_env:
        valid, _ = validate_env(interactive=True)
        if not valid:
            sys.exit(1)

    # 0.1. Docker liveness
    if not wait_for_docker():
        sys.exit(1)

    # 1. Run init
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Running init.py...")
    init_script = BASE_DIR / "init.py"
    subprocess.run([PYTHON, str(init_script)], check=True)

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
