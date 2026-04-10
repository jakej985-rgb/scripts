#!/usr/bin/env python3
"""
M3TAL Control Plane — Self-Healing Orchestrator
v2.0.0 — Production-Grade Bootstrap & Runtime Healing

Modular agents ensure system is bootable and resilient.
Supports --repair=[logs|state|all] and Degraded Mode.
"""

import json
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Any

# Root addition for utils
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent
AGENTS_DIR = BASE_DIR / "agents"

sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from utils.healing import (
    retry, is_writable, atomic_write_json, 
    acquire_healer_lock, release_healer_lock, log_event
)
from auth import inspect_users_file, reset_admin_user, resolve_users_path

# --- Configuration ------------------------------------------------------------
STATE_DIR = BASE_DIR / "state"
LOG_DIR = STATE_DIR / "logs"

REQUIRED_DIRS = [STATE_DIR, LOG_DIR, STATE_DIR / "health", STATE_DIR / "locks"]

REQUIRED_LOGS = [
    "monitor.log", "metrics.log", "anomaly.log", "decision.log",
    "reconcile.log", "registry.log", "observer.log", "scorer.log",
    "chaos.log", "supervisor.log", "healer.log"
]

STATE_FILE_DEFAULTS = {
    "metrics.json": {"system": {}, "containers": [], "timestamp": 0, "cpu": 0},
    "normalized_metrics.json": {},
    "anomalies.json": {"issues": []},
    "decisions.json": {"actions": []},
    "registry.json": {"containers": []},
    "health.json": {"status": "init", "timestamp": 0, "mode": "startup", "details": {}},
    "last_prune.json": {"ts": 0},
}

# --- State Management ---------------------------------------------------------
SYSTEM_STATUS = {
    "filesystem": "unknown",
    "logs": "unknown",
    "state": "unknown",
    "docker": "unknown",
    "auth": "unknown"
}

MODE = "startup"  # Default mode

def update_status(component: str, status: str):
    SYSTEM_STATUS[component] = status
    log_event("init", f"Component {component} status: {status}")

# --- Healing Agents -----------------------------------------------------------

def fs_agent(repair_mode: bool = False):
    """🧱 Filesystem Agent: Startup Scaffolding & Writability Checks."""
    try:
        for d in REQUIRED_DIRS:
            if not d.exists() or repair_mode:
                log_event("init", f"[FS] Creating/Repairing dir: {d}")
                d.mkdir(parents=True, exist_ok=True)
            
            if not is_writable(d):
                log_event("init", f"[FS] WARNING: {d} is NOT writable. Attempting repair...")
                # Transient dirs can be recreated
                if d.name in ["tmp", "health", "locks"]:
                    retry(lambda: (subprocess.run(["rm", "-rf", str(d)], check=True), d.mkdir(parents=True, exist_ok=True)))
                else:
                    log_event("init", f"[FS] FATAL: Core dir {d} is un-writable and non-recoverable.")
                    return False
        
        update_status("filesystem", "ok")
        return True
    except Exception as e:
        log_event("init", f"[FS] Agent failed: {e}")
        update_status("filesystem", "failed")
        return False

def log_agent(repair_mode: bool = False):
    """📄 Log Agent: Ensures all log files are available or falls back to stdout."""
    try:
        success_count = 0
        for name in REQUIRED_LOGS:
            path = LOG_DIR / name
            if not path.exists() or repair_mode:
                log_event("init", f"[LOG] Creating missing log: {name}")
                try:
                    retry(lambda: path.touch())
                    success_count += 1
                except:
                    log_event("init", f"[LOG] FAILED to touch {name}. Parent writable={is_writable(LOG_DIR)}")
            else:
                success_count += 1
        
        if success_count < len(REQUIRED_LOGS):
            update_status("logs", "degraded")
        else:
            update_status("logs", "ok")
        return True
    except Exception as e:
        log_event("init", f"[LOG] Agent failed: {e}. Falling back to stdout.")
        update_status("logs", "degraded")
        return True # Non-fatal

def state_agent(repair_mode: bool = False):
    """🧬 State Agent: Atomic repair and validation of JSON state files."""
    try:
        for name, default_data in STATE_FILE_DEFAULTS.items():
            path = STATE_DIR / name
            needs_fix = False
            
            if not path.exists() or repair_mode:
                needs_fix = True
            else:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        json.load(f)
                except:
                    log_event("init", f"[STATE] Corrupted state detected in {name}. Resetting...")
                    needs_fix = True
            
            if needs_fix:
                atomic_write_json(path, default_data)
        
        update_status("state", "ok")
        return True
    except Exception as e:
        log_event("init", f"[STATE] Agent failed: {e}")
        update_status("state", "failed")
        return False

def auth_agent():
    """🔐 Identity Agent: Non-blocking user baseline check."""
    try:
        users_path = resolve_users_path(REPO_ROOT / "dashboard")
        _, error = inspect_users_file(users_path=users_path)
        
        if error is not None:
            if sys.stdin.isatty() and MODE == "startup":
                log_event("init", f"[AUTH] Users file {error}. Starting interactive setup...")
                reset_admin_user(users_path=users_path)
            else:
                log_event("init", f"[AUTH] WARNING: Auth incomplete ({error}). Headless mode bypassing.")
                update_status("auth", "degraded")
                return True
        
        update_status("auth", "ok")
        return True
    except Exception as e:
        log_event("init", f"[AUTH] Agent failed: {e}")
        update_status("auth", "degraded")
        return True # Non-fatal

def docker_agent(repair_mode: bool = False):
    """🐳 Docker Agent: Smart orchestration with network/timeout recovery."""
    try:
        use_shell = os.name == "nt"
        # Network fix
        try:
            retry(lambda: subprocess.run(["docker", "network", "create", "m3tal"], 
                                       capture_output=True, shell=use_shell, check=True))
        except: pass 

        stacks = [("routing", REPO_ROOT / "docker" / "routing"), 
                  ("core", REPO_ROOT / "docker" / "core")]
        
        for name, sd in stacks:
            cf = sd / "docker-compose.yml"
            if not cf.exists(): continue
            
            def launch():
                # Runtime check: is the stack already running?
                if MODE == "runtime" and not repair_mode:
                    # Check if containers for this stack exist
                    check_cmd = ["docker", "compose", "-f", str(cf), "ps", "--format", "json"]
                    ps_res = subprocess.run(check_cmd, capture_output=True, text=True, shell=use_shell)
                    if ps_res.returncode == 0:
                        ps_data = []
                        try:
                            # docker compose ps --format json can be multiple lines of json objects or one list
                            out = ps_res.stdout.strip()
                            if out:
                                if out.startswith("["):
                                    ps_data = json.loads(out)
                                else:
                                    ps_data = [json.loads(l) for l in out.splitlines()]
                        except: pass
                        
                        if ps_data:
                            # If all containers are running/healthy, skip
                            running = [c for c in ps_data if c.get("State") == "running"]
                            if len(running) == len(ps_data):
                                return True
                            
                res = subprocess.run(["docker", "compose", "-f", str(cf), "up", "-d"], 
                                   capture_output=True, text=True, shell=use_shell)
                if res.returncode != 0:
                    if "syntax" in res.stderr.lower() or "no such file" in res.stderr.lower():
                        raise ValueError(f"Fatal Config Error: {res.stderr[:100]}")
                    raise RuntimeError(f"Transient Docker Error: {res.stderr[:100]}")
                return True

            try:
                retry(launch, attempts=2 if MODE == "runtime" else 3)
            except Exception as e:
                log_event("init", f"[DOCKER] Failed to launch {name}: {e}")
                update_status("docker", "partial")
        
        if SYSTEM_STATUS["docker"] == "unknown":
            update_status("docker", "ok")
        return True
    except Exception as e:
        log_event("init", f"[DOCKER] Agent failed: {e}")
        update_status("docker", "failed")
        return True # Non-fatal

def health_agent():
    """🩺 Health Agent: Strict readiness contract + observability logic."""
    try:
        # Minimum Viable Contract: Filesystem and State must be OK
        is_ready = (SYSTEM_STATUS["filesystem"] == "ok" and 
                    SYSTEM_STATUS["state"] == "ok")
        
        final_status = "healthy"
        if not is_ready:
            final_status = "failed"
        elif any(v in ["degraded", "partial", "failed"] for v in SYSTEM_STATUS.values()):
            final_status = "degraded"
        
        health_packet = {
            "status": final_status,
            "timestamp": int(time.time()),
            "mode": MODE,
            "details": SYSTEM_STATUS
        }
        
        atomic_write_json(STATE_DIR / "health.json", health_packet)
        log_event("init", f"Final Health Check: {final_status.upper()} (Ready: {is_ready})")
        return is_ready
    except Exception as e:
        print(f"Health Agent crashed: {e}")
        return False

# --- Main Orchestrator --------------------------------------------------------

def run_init(repair_scope: str = None):
    """Primary entry point for system initialization."""
    global MODE
    MODE = "startup"
    
    if not acquire_healer_lock():
        print("[INIT] Another instance/healer is active. Exiting.")
        return False

    try:
        log_event("init", f"--- M3TAL Self-Healing Startup (Repair Scope: {repair_scope}) ---")
        
        # 1. FS
        if not fs_agent(repair_mode=(repair_scope in ["all", "fs"])):
            return False
            
        # 2. Logs
        log_agent(repair_mode=(repair_scope in ["all", "logs"]))
        
        # 3. State
        if not state_agent(repair_mode=(repair_scope in ["all", "state"])):
            return False
            
        # 4. Auth
        auth_agent()
        
        # 5. Docker
        docker_agent(repair_mode=(repair_scope == "all"))
        
        # 6. Final Health
        return health_agent()

    finally:
        release_healer_lock()

if __name__ == "__main__":
    scope = None
    for arg in sys.argv:
        if arg.startswith("--repair="):
            scope = arg.split("=")[1]
        elif arg == "--repair":
            scope = "all"
            
    success = run_init(scope)
    if not success:
        print("Initialization FAILED. System non-viable.")
        sys.exit(1)
    print("Initialization COMPLETE.")
