#!/usr/bin/env python3
"""
M3TAL Control Plane — Self-Healing Orchestrator
v2.1.0 — Premium UI & Runtime Healing
"""

import json
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# Root addition for utils
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent
AGENTS_DIR = BASE_DIR / "agents"
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(REPO_ROOT / "dashboard"))
sys.path.insert(0, str(SCRIPTS_DIR))

from utils.healing import (
    retry, is_writable, atomic_write_json, 
    acquire_healer_lock, release_healer_lock, log_event
)
from auth import inspect_users_file, reset_admin_user, resolve_users_path
from progress_utils import (
    Header, ProgressBar, SubProgressBar, LiveList, Heartbeat, Spinner,
    CYAN, GREEN, YELLOW, RED, BOLD, END, DIM
)

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
HB: Optional[Heartbeat] = None
BAR: Optional[ProgressBar] = None

def t_log(msg: str, symbol: str = "•"):
    """Terminal & File Logger bridge."""
    log_event("init", msg)
    if HB:
        HB.log(msg, symbol=symbol)
    else:
        print(f"  {CYAN}{symbol}{END} {msg}")

def update_status(component: str, status: str):
    SYSTEM_STATUS[component] = status
    t_log(f"Component {component} status: {status}", symbol="✔" if status == "ok" else "⚠")

# --- Healing Agents -----------------------------------------------------------

def fs_agent(repair_mode: bool = False):
    """🧱 Filesystem Agent: Startup Scaffolding & Writability Checks."""
    if HB: HB.ping("Scaffolding directories")
    try:
        for d in REQUIRED_DIRS:
            if not d.exists() or repair_mode:
                t_log(f"[FS] Creating/Repairing dir: {d.name}")
                d.mkdir(parents=True, exist_ok=True)
            
            if not is_writable(d):
                t_log(f"[FS] WARNING: {d.name} is NOT writable. Attempting repair...", symbol="⚠")
                if d.name in ["tmp", "health", "locks"]:
                    retry(lambda: (subprocess.run(["rm", "-rf", str(d)], check=True), d.mkdir(parents=True, exist_ok=True)))
                else:
                    t_log(f"[FS] FATAL: Core dir {d.name} is un-writable.", symbol="✘")
                    return False
        
        update_status("filesystem", "ok")
        return True
    except Exception as e:
        t_log(f"[FS] Agent failed: {e}", symbol="✘")
        update_status("filesystem", "failed")
        return False

def log_agent(repair_mode: bool = False):
    """📄 Log Agent: Ensures all log files are available."""
    if HB: HB.ping("Touching logs")
    try:
        success_count = 0
        for name in REQUIRED_LOGS:
            path = LOG_DIR / name
            if not path.exists() or repair_mode:
                t_log(f"[LOG] Initializing {name}")
                try:
                    retry(lambda: path.touch())
                    success_count += 1
                except:
                    t_log(f"[LOG] FAILED to touch {name}", symbol="⚠")
            else:
                success_count += 1
        
        update_status("logs", "ok" if success_count == len(REQUIRED_LOGS) else "degraded")
        return True
    except Exception as e:
        t_log(f"[LOG] Agent failed: {e}. Falling back to stdout.", symbol="⚠")
        update_status("logs", "degraded")
        return True

def state_agent(repair_mode: bool = False):
    """🧬 State Agent: Atomic repair and validation of JSON state files."""
    if HB: HB.ping("Validating state JSON")
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
                    t_log(f"[STATE] Resetting corrupted {name}", symbol="⚠")
                    needs_fix = True
            
            if needs_fix:
                atomic_write_json(path, default_data)
        
        update_status("state", "ok")
        return True
    except Exception as e:
        t_log(f"[STATE] Agent failed: {e}", symbol="✘")
        update_status("state", "failed")
        return False

def auth_agent():
    """🔐 Identity Agent: Non-blocking user baseline check."""
    if HB: HB.ping("Checking identity baseline")
    try:
        users_path = resolve_users_path(REPO_ROOT / "dashboard")
        _, error = inspect_users_file(users_path=users_path)
        
        if error is not None:
            if sys.stdin.isatty() and MODE == "startup":
                t_log(f"[AUTH] Users file {error}. Starting setup...", symbol="⚠")
                if HB: HB.stop() # Pause HB for interactive prompt
                reset_admin_user(users_path=users_path)
                if HB: HB.start()
            else:
                t_log(f"[AUTH] Incomplete ({error}). Bypassing.", symbol="⚠")
                update_status("auth", "degraded")
                return True
        
        update_status("auth", "ok")
        return True
    except Exception as e:
        t_log(f"[AUTH] Agent failed: {e}", symbol="⚠")
        update_status("auth", "degraded")
        return True

def docker_agent(repair_mode: bool = False):
    """🐳 Docker Agent: Smart orchestration with network/timeout recovery."""
    if HB: HB.ping("Orchestrating Docker stacks")
    try:
        use_shell = os.name == "nt"
        try:
            retry(lambda: subprocess.run(["docker", "network", "create", "m3tal"], 
                                       capture_output=True, shell=use_shell, check=True))
            t_log("[DOCKER] Shared network 'm3tal' ready")
        except: pass 

        stacks = [("routing", REPO_ROOT / "docker" / "routing"), 
                  ("core", REPO_ROOT / "docker" / "core")]
        
        for name, sd in stacks:
            cf = sd / "docker-compose.yml"
            if not cf.exists(): continue
            
            t_log(f"[DOCKER] Orchestrating stack: {name}")
            
            # Sub-item: Detect expected services
            use_shell = os.name == "nt"
            conf_cmd = ["docker", "compose", "-f", str(cf), "config", "--services"]
            conf_res = subprocess.run(conf_cmd, capture_output=True, text=True, shell=use_shell)
            expected_services = conf_res.stdout.strip().splitlines() if conf_res.returncode == 0 else []
            total_svc = len(expected_services)
            
            sub_bar = SubProgressBar(total_svc)
            live_list = LiveList(expected_services)
            sub_bar.update(0, f"Initializing {total_svc} services")

            def launch():
                res = subprocess.run(["docker", "compose", "-f", str(cf), "up", "-d"], 
                                   capture_output=True, text=True, shell=use_shell)
                if res.returncode != 0:
                    raise RuntimeError(f"Docker Error: {res.stderr[:200]}")
                return True

            try:
                # 1. Start the stack
                retry(launch, attempts=2 if MODE == "runtime" else 3)
                
                # 2. Poll for readiness
                if total_svc > 0:
                    start_time = time.time()
                    while time.time() - start_time < 60: # 60s Smart Timeout
                        ps_res = subprocess.run(["docker", "compose", "-f", str(cf), "ps", "--format", "json"],
                                             capture_output=True, text=True, shell=use_shell)
                        if ps_res.returncode == 0:
                            out = ps_res.stdout.strip()
                            ps_data = []
                            try:
                                if out.startswith("["): ps_data = json.loads(out)
                                elif out: ps_data = [json.loads(l) for l in out.splitlines()]
                            except: pass
                            
                            ready_count = 0
                            for item in expected_services:
                                match = next((c for c in ps_data if c.get("Service") == item), None)
                                note = ""
                                if match:
                                    state = match.get("State", "unknown").lower()
                                    status_text = match.get("Status", "").lower()
                                    
                                    # Deep Inspect for non-running items
                                    if state not in ["running", "healthy"]:
                                        insp = subprocess.run(["docker", "inspect", match.get("Name", ""), "--format", "{{json .State}}"],
                                                           capture_output=True, text=True, shell=use_shell)
                                        if insp.returncode == 0:
                                            try:
                                                istate = json.loads(insp.stdout)
                                                exit_code = istate.get("ExitCode", 0)
                                                restarts = istate.get("RestartCount", 0)
                                                error = istate.get("Error", "")
                                                if restarts > 0: note = f"{restarts} restarts"
                                                if exit_code != 0: note += f", Exit {exit_code}"
                                                if error: note += f", {error[:20]}"
                                            except: pass

                                    # Smart State Mapping
                                    smart_state = state
                                    if "health: starting" in status_text: smart_state = "starting (health-check)"
                                    elif state == "running" and "unhealthy" in status_text: smart_state = "unhealthy"
                                    elif state == "running": smart_state = "healthy" if "healthy" in status_text else "running"
                                    elif state == "created": smart_state = "creating..."
                                    
                                    live_list.update(item, smart_state, note=note.strip(", "))
                                    if smart_state in ["running", "healthy"]: ready_count += 1
                                else:
                                    live_list.update(item, "preparing...")

                            sub_bar.update(ready_count, f"Processed {ready_count}/{total_svc}")
                            if ready_count >= total_svc: break
                        time.sleep(1.5)
                    
                    if ready_count < total_svc:
                         t_log(f"[DOCKER] Stack {name} timed out. Proceeding in DEGRADED mode.", symbol="⚠")
                         update_status("docker", "partial")
                
                # Lock the lines so next stack prints below
                live_list.reset()
                
            except Exception as e:
                t_log(f"[DOCKER] Stack {name} failed: {e}", symbol="⚠")
                update_status("docker", "partial")
                if 'live_list' in locals(): live_list.reset()
        
        if SYSTEM_STATUS["docker"] == "unknown":
            update_status("docker", "ok")
        return True
    except Exception as e:
        t_log(f"[DOCKER] Agent failed: {e}", symbol="✘")
        update_status("docker", "failed")
        return True

def health_agent():
    """🩺 Health Agent: Final readiness contract."""
    if HB: HB.ping("Finalizing system health")
    try:
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
        t_log(f"System Readiness: {final_status.upper()}", symbol="★" if is_ready else "✘")
        return is_ready
    except Exception as e:
        print(f"Health Agent crashed: {e}")
        return False

# --- Main Orchestrator --------------------------------------------------------

def run_init(repair_scope: str = None):
    """Primary entry point for system initialization."""
    global MODE, HB, BAR
    MODE = "startup"
    
    Header.show("M3TAL Self-Healing Init", f"Production Bootstrap — Repair: {repair_scope or 'None'}")
    
    if not acquire_healer_lock():
        print(f"  {RED}✘{END} Another instance is active. Exiting.")
        return False

    HB = Heartbeat()
    HB.start()
    BAR = ProgressBar(6, prefix="Init")
    HB.tether(BAR)

    try:
        # Step 1: FS
        BAR.update(0, "Filesystem")
        if not fs_agent(repair_mode=(repair_scope in ["all", "fs"])):
            return False
            
        # Step 2: Logs
        BAR.update(1, "Logs")
        log_agent(repair_mode=(repair_scope in ["all", "logs"]))
        
        # Step 3: State
        BAR.update(2, "State")
        if not state_agent(repair_mode=(repair_scope in ["all", "state"])):
            return False
            
        # Step 4: Auth
        BAR.update(3, "Auth")
        auth_agent()
        
        # Step 5: Docker
        BAR.update(4, "Docker")
        docker_agent(repair_mode=(repair_scope == "all"))
        
        # Step 6: Final Health
        BAR.update(5, "Health")
        ready = health_agent()
        BAR.update(6, "Complete")
        
        return ready

    finally:
        HB.stop()
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
        print(f"\n{RED}{BOLD}FATAL: Initialization failed. System non-viable.{END}")
        sys.exit(1)
    print(f"\n{GREEN}{BOLD}Initialization COMPLETE.{END}")
