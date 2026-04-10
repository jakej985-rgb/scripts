#!/usr/bin/env python3
"""
M3TAL Agent Runner — Autonomous Process Manager
v1.0.0 — Decoupled from supervisor.py

Launches and loops all agents with exponential backoff and central log routing.
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

# --- Context Anchoring --------------------------------------------------------
AGENTS_DIR = Path(__file__).resolve().parent
BASE_DIR = AGENTS_DIR.parent  # control-plane/
REPO_ROOT = BASE_DIR.parent

# Add support directories to system path
for path in [REPO_ROOT / "scripts", REPO_ROOT / "dashboard"]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

# --- Path System --------------------------------------------------------------
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
    ("tunnel",    "tunnel.py",       False),
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
    print(f"\n[{ts}] Agent Runner received signal {signum}. Shutting down agents...")
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
                    # Rex Fix Plan: Agents are persistent — no timeout
                    exit_code = proc.wait()
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
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] M3TAL Agent Runner launching...")

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

    # Wait for shutdown signal
    try:
        while not _shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown_event.set()

    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Waiting for agent threads to exit...")
    for t in threads:
        t.join(timeout=5)

    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Agent Runner shutdown complete.")


if __name__ == "__main__":
    main()
