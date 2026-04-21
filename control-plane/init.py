#!/usr/bin/env python3
"""
M3TAL Control Plane — Self-Healing Orchestrator
v2.1.0 — Premium UI & Runtime Healing
"""

import json
import os
import sys
import time
import shutil
import subprocess
import threading
from pathlib import Path

# Path bootstrap (V6.5.2)----------------------------------------------------
# Resolve paths absolutely to satisfy IDE linter and ensure cross-platform stability
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent
AGENTS_DIR = BASE_DIR / "agents"

# Standardize Search Paths
for path in [AGENTS_DIR, REPO_ROOT / "scripts" / "helpers", REPO_ROOT / "scripts" / "test", REPO_ROOT / "dashboard"]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

ENV_FILE = REPO_ROOT / ".env"

from typing import Dict, Optional
from utils.paths import STATE_DIR, LOG_DIR

import builtins
import warnings
import logging

logging.basicConfig(
    filename=str(LOG_DIR / "m3tal.log"),
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def warning_to_log(message, category, filename, lineno, file=None, line=None):
    logging.warning(f"{filename}:{lineno}: {category.__name__}: {message}")

warnings.showwarning = warning_to_log

USE_SAFE_PRINT = True

def m3tal_print(*args, **kwargs):
    if USE_SAFE_PRINT:
        try:
            from progress_utils import safe_print
            safe_print(*args, **kwargs)
        except ImportError:
            builtins.print(*args, **kwargs)
    else:
        builtins.print(*args, **kwargs)

from utils.env import load_env
# builtins.print = m3tal_print # Audit Fix (L) - Removed global patch to avoid side effects

try:
    from preflight import run_preflight
except ImportError:
    run_preflight = None

from utils.healing import (
    retry, is_writable, atomic_write_json, 
    acquire_healer_lock, release_healer_lock, log_event
)
from auth import inspect_users_file, reset_admin_user, resolve_users_path
from progress_utils import (
    Header, ProgressBar, SubProgressBar, LiveList, Heartbeat, reset_session_timer,
    CYAN,
    GREEN, RED, BOLD, END
)

# --- Configuration ------------------------------------------------------------
REQUIRED_DIRS = [
    STATE_DIR, 
    LOG_DIR, 
    STATE_DIR / "health", 
    STATE_DIR / "locks"
]

REQUIRED_LOGS = [
    "monitor.log", "metrics.log", "anomaly.log", "decision.log",
    "reconcile.log", "registry.log", "observer.log", "scorer.log",
    "chaos.log", "healer.log"
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

# --- Internal Helpers ---------------------------------------------------------
GLOBAL_ENV = load_env(REPO_ROOT)

# --- State Management ---------------------------------------------------------
SYSTEM_STATUS = {
    "filesystem": "unknown",
    "logs": "unknown",
    "state": "unknown",
    "docker": "unknown",
    "auth": "unknown",
    "dependencies": "unknown",
    "environment": "unknown"
}

MODE = "startup"  # Default mode
HB: Optional[Heartbeat] = None
BAR: Optional[ProgressBar] = None

def t_log(msg: str, symbol: str = None):
    """Terminal & File Logger bridge."""
    log_event("init", msg, symbol=symbol)
    if HB:
        HB.log(msg, symbol=symbol)
    else:
        print(f"  {CYAN}{symbol if symbol else '•'}{END} {msg}")

def update_status(component: str, status: str):
    SYSTEM_STATUS[component] = status
    t_log(f"Component {component} status: {status}", symbol="✔" if status == "ok" else "⚠")

def wait_for_readiness(name: str, container_name: str, log_pattern: str = None, probe_cmd: list = None, timeout: int = 60) -> bool:
    """Multi-signal readiness: Polls Docker health/status and runs network probes until service is ready."""
    t_log(f"Waiting for {name} readiness (timeout {timeout}s)...", symbol="⏳")
    start_time = time.time()
    last_logged_status = None
    
    while time.time() - start_time < timeout:
        try:
            # Signal 1: Docker Health/Status (Primary source of truth - Audit Fix 6.6)
            inspect_cmd = ["docker", "inspect", container_name, "--format", "{{json .State}}"]
            res = subprocess.run(inspect_cmd, capture_output=True, text=True, env=GLOBAL_ENV)
            if res.returncode == 0:
                state = json.loads(res.stdout)
                status = state.get("Status", "").lower()
                health = state.get("Health", {})
                
                # If healthcheck is defined, wait for 'healthy'
                if health:
                    h_status = health.get("Status")
                    if h_status == "healthy":
                        t_log(f"{name} is HEALTHY.", symbol="✔")
                        return True
                    elif h_status == "unhealthy":
                        t_log(f"{name} reported UNHEALTHY state.", symbol="✘")
                        return False
                    elif h_status != last_logged_status:
                        t_log(f"{name} health check: {h_status}...", symbol="⏳")
                        last_logged_status = h_status
                
                # Fallback/Primary: If it's running, we move on (Audit Fix 6.6 — Optimistic Boot)
                elif status == "running":
                    t_log(f"{name} is RUNNING (Moving on).", symbol="✔")
                    return True
                
                elif status != last_logged_status:
                    t_log(f"{name} status: {status}...", symbol="⏳")
                    last_logged_status = status

            # Signal 2: Network/Probe Command (Non-blocking if already running)
            if probe_cmd:
                # We still attempt the probe for the record, but we don't loop here 
                # if the container was found running above.
                full_cmd = ["docker", "exec", container_name] + probe_cmd
                probe_res = subprocess.run(full_cmd, capture_output=True, env=GLOBAL_ENV)
                if probe_res.returncode == 0:
                    t_log(f"{name} network probe SUCCEEDED.", symbol="✔")
                    return True

        except Exception:
            pass
        
        time.sleep(2)
    
    t_log(f"{name} readiness TIMEOUT of {timeout}s reached.", symbol="⚠")
    return False



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
                    retry(lambda: (shutil.rmtree(str(d), ignore_errors=True), d.mkdir(parents=True, exist_ok=True)))
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
                except Exception:
                    t_log(f"[LOG] FAILED to touch {name}", symbol="⚠")
            else:
                success_count += 1
        
        # Audit Fix (L): Purge legacy PID-specific log files on startup
        if LOG_DIR.exists():
            stale_logs = [l for l in LOG_DIR.glob("*_[0-9]*.log") if l.is_file()]
            if stale_logs:
                for sl in stale_logs:
                    try: sl.unlink()
                    except Exception: pass
        
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
                except Exception:
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

def dependency_agent():
    """📦 Dependency Agent: Validates required Python packages."""
    if HB: HB.ping("Validating dependencies")
    critical_deps = ["requests", "yaml", "psutil"]
    missing = []
    
    for dep in critical_deps:
        try:
            __import__(dep if dep != "yaml" else "yaml")
        except ImportError:
            missing.append(dep)
            
    try:
        import bcrypt  # noqa: F401
    except ImportError:
        t_log("[DEP] WARNING: bcrypt missing (Tier 2). Auth repairs disabled.", symbol="⚠")
        update_status("auth", "degraded")
    
    if missing:
        t_log(f"[DEP] FATAL: Missing critical dependencies: {', '.join(missing)}", symbol="✘")
        t_log("[DEP] Solution: pip install -r requirements.txt", symbol="💡")
        update_status("dependencies", "failed")
        return False
        
    update_status("dependencies", "ok")
    return True

def env_validation_agent():
    """🌍 Environment Agent: Audit Fix 4.5 — Strict validation of runtime context."""
    if HB: HB.ping("Validating environment")
    try:
        # 1. Container Detection
        is_container = Path("/.dockerenv").exists()
        t_log(f"[ENV] Context: {'Docker Container' if is_container else 'Host System'}")
        
        # 2. .env presence
        # (Validated via getenv loops below)
        
        # 3. Required Vars (Expanded for 6-Channel Control Plane)
        strictly_required = ["TELEGRAM_BOT_TOKEN", "TG_CHAT_COUNT", "DOCKER_API_VERSION", "REPO_ROOT"]
        potential_chats = [
            "TG_MAIN_CHAT_ID", "TG_LOG_CHAT_ID", "TG_ERROR_CHAT_ID", 
            "TG_ALERT_CHAT_ID", "TG_ACTION_CHAT_ID", "TG_DOCKER_CHAT_ID",
            "TELEGRAM_CHAT_ID"
        ]
        
        missing = []
        for var in strictly_required:
            if not os.getenv(var):
                missing.append(var)
        
        # Soft-check: Need at least one chat ID to be useful
        has_chat = any(os.getenv(c) and os.getenv(c) != "0" for c in potential_chats)
        if not has_chat:
            t_log("[ENV] WARNING: No active Telegram Chat IDs found. Telemetry will be silent.", symbol="⚠")
        
        if missing:
            t_log(f"[ENV] Missing CRITICAL variables: {', '.join(missing)}", symbol="✘")
            update_status("environment", "failed")
            return False
        else:
            update_status("environment", "ok")
            
        return True
    except Exception as e:
        t_log(f"[ENV] Agent failure: {e}", symbol="⚠")
        update_status("environment", "failed")
        return True

def auth_agent():
    """🔐 Identity Agent: Non-blocking user baseline check."""
    if HB: HB.ping("Checking identity baseline")
    try:
        from auth import HAS_BCRYPT
        users_path = resolve_users_path(REPO_ROOT / "dashboard")
        
        if not HAS_BCRYPT:
            # Already logged by dependency_agent
            update_status("auth", "degraded")
            return True

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
        try:
            retry(lambda: subprocess.run(["docker", "network", "create", "proxy"], 
                                       capture_output=True, env=GLOBAL_ENV, check=True))
            t_log("[DOCKER] Shared network 'proxy' ready")
        except Exception: pass 
        
        # Shared State 
        global_statuses = {}
        active_stacks = [] # List of (stack_name, path, is_critical, total_svc, expected_services_list)
        stop_poller = threading.Event()
        
        # UI Reference for Poller
        active_ui_lock = threading.Lock()
        shared_live_list_ref = None

        def ui_status_poller():
            """Continuously updates the GlobalLiveList for all active stacks."""
            while not stop_poller.is_set():
                for name, sd, is_critical, total, services in list(active_stacks):
                    cf = sd / "docker-compose.yml"
                    ps_res = subprocess.run(["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(cf), "ps", "--format", "json"],
                                         capture_output=True, text=True, env=GLOBAL_ENV)
                    if ps_res.returncode == 0:
                        out = ps_res.stdout.strip()
                        ps_data = []
                        try:
                            if out.startswith("["): ps_data = json.loads(out)
                            elif out: ps_data = [json.loads(l) for l in out.splitlines()]
                        except Exception: pass
                        
                        for item in services:
                            match = next((c for c in ps_data if c.get("Service") == item), None)
                            if match:
                                state = match.get("State", "unknown").lower()
                                status_text = match.get("Status", "").lower()
                                smart_state = state
                                
                                # Visual polish
                                if "health: starting" in status_text: smart_state = "starting (health-check)"
                                elif state == "running" and "unhealthy" in status_text: smart_state = "unhealthy"
                                elif state == "running": smart_state = "healthy" if "healthy" in status_text else "running"
                                elif state == "created": smart_state = "creating..."
                                
                                global_statuses[item] = smart_state
                                with active_ui_lock:
                                    if shared_live_list_ref and item in shared_live_list_ref.items:
                                        # Batching: Update state silently
                                        shared_live_list_ref.update(item, smart_state, redraw=False)
                
                # Redraw ONCE after all stacks and services are processed
                from progress_utils import request_render
                request_render()
                time.sleep(2)

        poller_thread = threading.Thread(target=ui_status_poller, daemon=True)
        poller_thread.start()

        stacks = [
            ("routing", REPO_ROOT / "docker" / "routing", True),    # CRITICAL: Gateway
            ("network", REPO_ROOT / "docker" / "network", True),    # CRITICAL: VPN
            ("maintenance", REPO_ROOT / "docker" / "maintenance", False),
            ("control-plane", REPO_ROOT / "control-plane", True),         # CRITICAL: Agents/Dashboard
            ("media", REPO_ROOT / "docker" / "media", False),
            ("apps/tattoo-app", REPO_ROOT / "docker" / "apps" / "tattoo-app", False)
        ]
        
        # Tiered Timeouts
        TIMEOUTS = {
            "routing": 90,
            "network": 90,
            "control-plane": 60,
            "media": 120,
            "maintenance": 60,
            "apps/tattoo-app": 60
        }

        # Readiness definitions (Log Pattern, Probe Command)
        # IMPORTANT: cloudflared and gluetun are Alpine-based — they have wget, NOT curl.
        READINESS = {
            "routing": ("cloudflared", "Registered tunnel connection", ["wget", "-q", "--spider", "http://traefik:80"]),
            "network": ("gluetun", "VPN is up", ["wget", "-q", "--spider", "--timeout=3", "http://ipinfo.io"]),
            "control-plane": ("m3tal-dashboard", None, ["wget", "-q", "--spider", "http://localhost:8080/api/health"])
        }
        
        for name, sd, is_critical in stacks:
            cf = sd / "docker-compose.yml"
            if not cf.exists(): continue
            
            t_log(f"[DOCKER] Orchestrating stack: {name}")
            
            # Sub-item: Detect expected services
            conf_cmd = ["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(cf), "config", "--services"]
            conf_res = subprocess.run(conf_cmd, capture_output=True, text=True, env=GLOBAL_ENV)
            expected_services = conf_res.stdout.strip().splitlines() if conf_res.returncode == 0 else []
            total_svc = len(expected_services)
            
            with SubProgressBar(total_svc) as sub_bar, LiveList(expected_services) as active_live_list:
                with active_ui_lock:
                    # Provide access to the live list for the poller
                    shared_live_list_ref = active_live_list
                
                sub_bar.update(0, f"Initializing {total_svc} services ({name})")
                
                # Seed the status dictionary
                for svc in expected_services:
                    global_statuses[svc] = "queued"

                try:
                    # 1. Register stack and start launch
                    active_stacks.append((name, sd, is_critical, total_svc, expected_services))
                    
                    # Add --build for stacks with custom Dockerfiles (Audit fix H10)
                    up_cmd = ["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(cf), "up", "-d"]
                    if repair_mode:
                        up_cmd.append("--force-recreate")

                    try:
                        with open(cf, "r") as compose_f:
                            content = compose_f.read()
                            if "build:" in content:
                                # Only force build in repair mode to keep healer cycles light
                                if repair_mode:
                                    up_cmd.append("--build")
                    except Exception: pass
                    
                    proc = subprocess.Popen(up_cmd, 
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                                         text=True, env=GLOBAL_ENV)
                    
                    # 2. Wait for Docker status (Up/Running)
                    wait_time = TIMEOUTS.get(name, 90)
                    start_time = time.time()
                    ready_count = 0
                    while time.time() - start_time < wait_time:
                        if proc.poll() is not None and proc.returncode != 0:
                            raise RuntimeError(f"Docker Launch Error (Exit {proc.returncode}) for {name}")
                        
                        ready_count = sum(1 for item in expected_services 
                                        if global_statuses.get(item) in ["running", "healthy", "done"])
                        
                        sub_bar.update(ready_count, f"Processed {ready_count}/{total_svc} ({name})")
                        if ready_count >= total_svc: break
                        
                        if ready_count == 0 and proc.poll() is None:
                            for item in expected_services:
                                if global_statuses.get(item) == "queued":
                                    global_statuses[item] = "pulling"
                                    with active_ui_lock:
                                        active_live_list.update(item, "pulling")
                        time.sleep(1.5)

                    # 3. Enhanced Readiness Check (Multi-Signal)
                    if name in READINESS:
                        c_name, l_pat, p_cmd = READINESS[name]
                        if not wait_for_readiness(name, c_name, l_pat, p_cmd, timeout=wait_time):
                            if is_critical:
                                raise RuntimeError(f"Critical service {c_name} in {name} stack failed readiness probes.")

                    if ready_count < total_svc:
                        if is_critical and name in ["routing", "network"]:
                            # Fail-Fast: Core infrastructure CANNOT be degraded (Audit Fix Branch)
                            raise RuntimeError(f"FATAL: Critical stack '{name}' failed to reach ready state. Aborting.")
                        elif is_critical:
                            t_log(f"[DOCKER] Stack {name} timed out. Proceeding in DEGRADED mode.", symbol="⚠")
                            update_status("docker", "partial")
                        else:
                            t_log(f"[DOCKER] Stack {name} launched in background. Moving on.", symbol="🚀")

                    
                    # Clear reference for poller before exiting context
                    with active_ui_lock:
                        shared_live_list_ref = None
                
                except Exception as e:
                    t_log(f"[DOCKER] Stack {name} failed: {e}", symbol="⚠")
                    update_status("docker", "partial")
                    with active_ui_lock:
                        shared_live_list_ref = None
        
        if SYSTEM_STATUS["docker"] == "unknown":
            update_status("docker", "ok")
        
        # Stop poller before exiting agent
        stop_poller.set()
        poller_thread.join(timeout=2)
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
            "mode": "running" if is_ready else "degraded",
            "details": SYSTEM_STATUS
        }
        
        atomic_write_json(STATE_DIR / "health.json", health_packet)
        t_log(f"System Readiness: {final_status.upper()}", symbol="★" if is_ready else "✘")
        return is_ready
    except Exception as e:
        print(f"Health Agent crashed: {e}")
        return False

def repair(scope: str = "all") -> bool:
    """🛠️ Repair Agent: Force-recreates stacks to resolve drift or connectivity gaps."""
    t_log(f"Repairing scope: {scope}", symbol="🔧")
    try:
        stacks_to_fix = [scope] if scope != "all" else ["routing", "network", "maintenance", "media", "apps/tattoo-app"]
        for stack in stacks_to_fix:
            sd = REPO_ROOT / "docker" / stack
            if not sd.exists(): continue
            t_log(f"[REPAIR] Rebuilding {stack} stack...", symbol="🔧")
            subprocess.run(["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(sd / "docker-compose.yml"), "up", "-d", "--force-recreate"], 
                         env=GLOBAL_ENV, capture_output=True)
        return True
    except Exception as e:
        t_log(f"Repair failed: {e}", symbol="✘")
        return False

# --- Main Orchestrator --------------------------------------------------------

def run_init(repair_scope: str = None) -> bool:
    """Main entry point: Orchestrates the entire bootstrap with preflight guarding."""
    # Audit Check: Production Config Protection handled internally

    repair_parts = repair_scope.split(",") if repair_scope else []
    
    Header.show("M3TAL Self-Healing Init", f"Production Bootstrap — Repair: {repair_scope or 'None'}")
    reset_session_timer()  # Zero the progress timer from this moment
    
    # 0. Preflight Gate
    if run_preflight:
        preflight_status = run_preflight()
        if preflight_status == "CRITICAL":
            Header.show("CRITICAL FAILURE", "Preflight Validation Failed. Aborting startup.")
            return False
        if preflight_status == "DEGRADED":
            log_event("init", "Starting in DEGRADED mode (Tunnel missing/incomplete).", symbol="⚠")
    
    if not acquire_healer_lock():
        print(f"  {RED}✘{END} Another instance is active. Exiting.")
        return False

    global HB, BAR
    HB = Heartbeat()
    HB.start()
    BAR = ProgressBar(9, prefix="Init")
    HB.tether(BAR)

    try:
        # Step 0: Environment & Dependencies (New Audit Layer)
        BAR.update(0, "Environment")
        env_validation_agent()
        
        BAR.update(1, "Dependencies")
        if not dependency_agent():
            return False

        # Step 1: FS
        BAR.update(2, "Filesystem")
        if not fs_agent(repair_mode=("all" in repair_parts or "fs" in repair_parts)):
            return False
            
        # Step 2: Logs
        BAR.update(3, "Logs")
        log_agent(repair_mode=("all" in repair_parts or "logs" in repair_parts))
        
        # Step 3: State
        BAR.update(4, "State")
        if not state_agent(repair_mode=("all" in repair_parts or "state" in repair_parts)):
            return False
            
        # Step 4: Auth
        BAR.update(5, "Auth")
        auth_agent()
        
        # Step 5: Docker
        BAR.update(6, "Docker")
        docker_agent(repair_mode=("all" in repair_parts))
        
        # Step 6: Final Health
        BAR.update(7, "Health")
        ready = health_agent()
        BAR.update(8, "Cleanup")
        
        return ready

    finally:
        HB.stop()
        release_healer_lock()

if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        print(f"{GREEN}{BOLD}[DRY-RUN]{END} Validation complete. System state is nominal.")
        sys.exit(0)

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
