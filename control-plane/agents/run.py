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

# --- Path System Bootstrap ----------------------------------------------------
AGENTS_DIR = Path(__file__).resolve().parent  # control-plane/agents/
sys.path.append(str(AGENTS_DIR))

from utils.paths import REPO_ROOT, CONTROL_PLANE, STATE_DIR, LOG_DIR, RESTARTS_JSON
from utils.healing import atomic_write_json
import json

BASE_DIR = CONTROL_PLANE

# Add support directories to system path
for path in [REPO_ROOT / "scripts", REPO_ROOT / "dashboard"]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

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
    ("healer",    "healer.py",       False),
    ("notify",    "notify.py",       False),
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

# --- Stability Logic ----------------------------------------------------------

def _get_restart_state() -> dict:
    if RESTARTS_JSON.exists():
        try:
            return json.loads(RESTARTS_JSON.read_text())
        except:
            return {}
    return {}

def _check_stability(name: str) -> bool:
    """Returns True if agent is stable, False if it should be paused."""
    state = _get_restart_state()
    agent_data = state.get(name, {"count": 0, "last_fail": 0, "pause_until": 0})
    now = time.time()

    # 1. Reset if stable for > 10 minutes
    if now - agent_data["last_fail"] > 600:
        agent_data["count"] = 0
    
    # 2. Check if currently in a pause window
    if now < agent_data["pause_until"]:
        return False
    
    return True

def _record_failure(name: str):
    """Records a failure and triggers backoff if unstable."""
    state = _get_restart_state()
    agent_data = state.get(name, {"count": 0, "last_fail": 0, "pause_until": 0})
    now = time.time()

    # Reset counter if last fail was long ago
    if now - agent_data["last_fail"] > 600:
        agent_data["count"] = 1
    else:
        agent_data["count"] += 1

    agent_data["last_fail"] = now

    # Stability Guard: 5 fails in 60s -> 5m pause
    if agent_data["count"] >= 5 and (now - agent_data["last_fail"] < 60):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] STABILITY_WARNING: {name} unstable. Pausing for 5m.")
        agent_data["pause_until"] = now + 300
    
    state[name] = agent_data
    atomic_write_json(RESTARTS_JSON, state)

def run_agent(name: str, script: str) -> None:
    """Run a single agent in a supervised loop with adaptive backoff."""
    while not _shutdown_event.is_set():
        if not _check_stability(name):
            time.sleep(10)
            continue

        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] Starting {name}...")
        log_path = LOG_DIR / f"{name}.log"

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

        if exit_code != 0:
            _record_failure(name)
            # Audit fix 2.7: True exponential backoff
            state = _get_restart_state()
            fail_count = state.get(name, {}).get("count", 1)
            wait_time = min(2**fail_count, 30)
            ts_err = time.strftime("%H:%M:%S")
            print(f"[{ts_err}] {name} failed. Retrying in {wait_time}s...")
            time.sleep(wait_time)
        else:
            time.sleep(2)


# --- Main Entry ---------------------------------------------------------------

def main() -> None:
    ts = time.strftime("%H:%M:%S")
    
    # Audit fix 2.5: Host vs Container Guard
    # Prevent duplicate agents if the m3tal-runtime container is already active
    # Skip this check if we are ALREADY inside the container
    if os.getenv("IN_CONTAINER") != "true":
        try:
            use_shell = os.name == "nt"
            check_cmd = ["docker", "ps", "--filter", "name=m3tal-runtime", "--filter", "status=running", "-q"]
            res = subprocess.run(check_cmd, capture_output=True, text=True, shell=use_shell)
            if res.returncode == 0 and res.stdout.strip():
                print(f"[{ts}] ABORT: m3tal-runtime container is already running. Terminating host-side runner.")
                sys.exit(0)
        except Exception:
            pass # Fallback to host-side execution if docker is inaccessible

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
