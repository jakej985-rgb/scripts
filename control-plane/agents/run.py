import os
import signal
import subprocess
import sys
import threading
import time
import random
import json
from pathlib import Path

# --- Path System Bootstrap ----------------------------------------------------
AGENTS_DIR = Path(__file__).resolve().parent  # control-plane/agents/
CONTROL_PLANE = AGENTS_DIR.parent             # control-plane/
sys.path.append(str(AGENTS_DIR))
sys.path.append(str(CONTROL_PLANE))

from utils.paths import CONTROL_PLANE, AGENTS_DIR, LOG_DIR, STATE_DIR, RESTARTS_JSON, ensure_dirs, TIERS
from utils.healing import atomic_write_json
from utils.guards import acquire_lock, release_lock, is_pid_running

# Telegram System Integration (v3 Layered)
from config.telegram import validate as validate_telegram
from agents import telegram

PYTHON = sys.executable

# --- Agent Registry -----------------------------------------------------------
# Sorted by Tier (Tier 1 first)
AGENTS = [
    ("leader",    "leader.py"),
    ("registry",  "registry.py"),
    ("monitor",   "monitor.py"),
    ("metrics",   "metrics.py"),
    ("scaling",   "scaling.py"),
    ("anomaly",   "anomaly.py"),
    ("decision",  "decision.py"),
    ("reconcile", "reconcile.py"),
    ("health_score", "health_score.py"),
    ("observer",  "observer.py"),
    ("tunnel",    "tunnel.py"),
    ("network_guard", "network_guard.py"),
    ("healer",    "healer.py"),
    ("notify",    "notify.py"),
]

# --- Master Locking -----------------------------------------------------------
RUNNER_LOCK = "agents_runner"

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
    print(f"\n[{ts}] Agent Runner received signal {signum}. Shutting down...")
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

# --- Restart & Stability ------------------------------------------------------

def _get_restart_state() -> dict:
    if RESTARTS_JSON.exists():
        try:
            return json.loads(RESTARTS_JSON.read_text())
        except Exception:
            return {}
    return {}

def _check_stability(name: str) -> bool:
    state = _get_restart_state()
    agent_data = state.get(name, {"count": 0, "last_fail": 0, "pause_until": 0})
    now = time.time()

    if now - agent_data["last_fail"] > 600:
        agent_data["count"] = 0
    
    if now < agent_data["pause_until"]:
        return False
    
    return True

def _record_failure(name: str):
    state = _get_restart_state()
    agent_data = state.get(name, {"count": 0, "last_fail": 0, "pause_until": 0})
    now = time.time()

    if now - agent_data["last_fail"] > 600:
        agent_data["count"] = 1
    else:
        agent_data["count"] += 1

    agent_data["last_fail"] = now

    # Stability Guard: 5 fails in 60s -> 5m pause
    if agent_data["count"] >= 5 and (now - agent_data["last_fail"] < 60):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] STABILITY_CRITICAL: {name} unstable (5 fails in 60s). Pausing for 5m.")
        agent_data["pause_until"] = now + 300
    
    state[name] = agent_data
    atomic_write_json(RESTARTS_JSON, state)

def run_agent(name: str, script: str) -> None:
    """Run a single agent in a supervised loop with jittered backoff."""
    env = os.environ.copy()
    env["M3TAL_ORCHESTRATOR"] = "1"
    env["M3TAL_ORCHESTRATED"] = "1"  # Suppresses stdout handler in child loggers
    
    # Ensure children can see control-plane root (Audit Phase 4)
    python_path = env.get("PYTHONPATH", "")
    new_path = f"{CONTROL_PLANE}{os.pathsep}{python_path}" if python_path else str(CONTROL_PLANE)
    env["PYTHONPATH"] = new_path
    
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
                    env=env
                )
                _register_child(proc)
                try:
                    exit_code = proc.wait()
                finally:
                    _unregister_child(proc)
        except Exception as e:
            exit_code = 1
            print(f"[{time.strftime('%H:%M:%S')}] ERROR: {name}: {e}")

        if _shutdown_event.is_set():
            break

        if exit_code != 0:
            _record_failure(name)
            # Restart Backoff (V4): 10s base + 0-5s jitter
            jitter = random.uniform(0, 5)
            wait_time = 10 + jitter
            ts_err = time.strftime("%H:%M:%S")
            print(f"[{ts_err}] {name} failed. Retrying in {int(wait_time)}s...")
            time.sleep(wait_time)
        else:
            time.sleep(2)

# --- Main Entry ---------------------------------------------------------------

def main() -> None:
    ts = time.strftime("%H:%M:%S")
    ensure_dirs()
    
    # 1. Initialize Telemetry System
    if validate_telegram():
        telegram.start()

    print(f"[{ts}] M3TAL Agent Runner launching...")

    # 1.0 Clean up stale locks (Audit fix 4.8)
    # If the runner crashed previously, it might have left locking debris.
    lock_dir = STATE_DIR / "locks"
    if lock_dir.exists():
        for lock in lock_dir.glob("*.pid"):
            try:
                # We don't delete the runner lock if it's currently held (check logic)
                if lock.name != f"{RUNNER_LOCK}.pid":
                    # Audit Fix 4.8: Only unlink if the PID is actually dead
                    try:
                        with open(lock, 'r') as f:
                            content = f.read().split(',')
                            if content:
                                old_pid = int(content[0])
                                if not is_pid_running(old_pid):
                                    lock.unlink()
                            else:
                                lock.unlink() # Empty/Broken
                    except (ValueError, IndexError, OSError):
                        lock.unlink() 
            except Exception: pass

    threads: list[threading.Thread] = []
    try:
        # PID 1 Hardening: If we are PID 1 (Docker), we are the master. 
        # Purge runner lock to ensure we can always start.
        if os.getpid() == 1:
            lock_path = STATE_DIR / "locks" / f"{RUNNER_LOCK}.pid"
            if lock_path.exists():
                print(f"[{time.strftime('%H:%M:%S')}] PID 1 detected. Purging main runner lock.")
                try: lock_path.unlink()
                except Exception: pass

        if not acquire_lock(RUNNER_LOCK):
            print(f"[{time.strftime('%H:%M:%S')}] FATAL: Another Agent Runner is already active. Exiting.")
            sys.exit(1)

        # 1.1 Wait for System Readiness (init.py must finish)
        health_file = STATE_DIR / "health.json"
        while not _shutdown_event.is_set():
            if health_file.exists():
                try:
                    health = json.loads(health_file.read_text())
                    # Acceptance: Mode 'running' OR 'degraded' (Audit fix 4.9)
                    if health.get("mode") in ["running", "degraded"]:
                        print(f"[{time.strftime('%H:%M:%S')}] System ready ({health.get('mode')}). Releasing agents...")
                        break
                except Exception:
                    pass
            print(f"[{time.strftime('%H:%M:%S')}] System INITIALIZING... waiting for bootstrap.")
            time.sleep(5)

        if _shutdown_event.is_set():
            return

        # 2. Tiered Launching (Tier 1 first)
        tier1 = [a for a in AGENTS if TIERS.get(a[0], 2) == 1]
        tier2 = [a for a in AGENTS if TIERS.get(a[0], 2) == 2]

        for name, script in tier1:
            t = threading.Thread(target=run_agent, args=(name, script), name=f"agent-{name}")
            threads.append(t)
            t.start()
            time.sleep(1) # Small stagger

        # Wait for Tier 1 to settle
        time.sleep(3)

        for name, script in tier2:
            t = threading.Thread(target=run_agent, args=(name, script), name=f"agent-{name}")
            threads.append(t)
            t.start()
            time.sleep(0.5)

        print(f"[{time.strftime('%H:%M:%S')}] All agents launched.")

        while not _shutdown_event.is_set():
            time.sleep(1)

    except KeyboardInterrupt:
        _shutdown_event.set()
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] FATAL ERROR in Runner: {e}")
        _shutdown_event.set()
    finally:
        print(f"[{time.strftime('%H:%M:%S')}] Waiting for threads to exit...")
        # Local copy to avoid modification during join
        # Join threads outside the lock to avoid deadlocks with _unregister_child
        for t in threads:
            t.join(timeout=2)

        release_lock(RUNNER_LOCK)
        print(f"[{time.strftime('%H:%M:%S')}] Agent Runner shutdown complete.")

if __name__ == "__main__":
    main()
