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
import threading
from pathlib import Path

# --- Path System Bootstrap ----------------------------------------------------
# Resolve paths absolutely to satisfy IDE linter and ensure cross-platform stability
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent
AGENTS_DIR = BASE_DIR / "agents"

# Standardize Search Paths
for path in [AGENTS_DIR, REPO_ROOT / "scripts" / "helpers", REPO_ROOT / "scripts" / "test", REPO_ROOT / "dashboard"]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

from typing import Dict, Any, Optional
from utils.paths import CONTROL_PLANE, STATE_DIR, LOG_DIR, SCRIPTS_DIR, ENV_TELEGRAM_TOKEN, ENV_TELEGRAM_CHAT
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
    Header, ProgressBar, SubProgressBar, LiveList, Heartbeat, Spinner,
    CYAN, GREEN, YELLOW, RED, BOLD, END, DIM
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

# --- Internal Helpers ---------------------------------------------------------
def load_env() -> Dict[str, str]:
    """Surgically load .env file into a dictionary for subprocess propagation."""
    env = os.environ.copy()
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    # Strip inline comments, whitespace, and quotes
                    v = v.split("#")[0].strip()
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    env[k.strip()] = v
                    os.environ[k.strip()] = v
    # Force REPO_ROOT for Docker
    env["REPO_ROOT"] = str(REPO_ROOT)
    os.environ["REPO_ROOT"] = str(REPO_ROOT)
    return env

GLOBAL_ENV = load_env()

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
    """Multi-signal readiness: Polls logs and runs network probes until service is ready."""
    t_log(f"Waiting for {name} readiness (timeout {timeout}s)...", symbol="⏳")
    start_time = time.time()
    use_shell = os.name == "nt"
    
    while time.time() - start_time < timeout:
        # Signal 1: Log Pattern
        if log_pattern:
            try:
                log_res = subprocess.run(["docker", "logs", "--tail", "50", container_name], 
                                      capture_output=True, text=True, shell=use_shell, env=GLOBAL_ENV)
                if log_pattern in log_res.stdout or log_pattern in log_res.stderr:
                    t_log(f"{name} log signal caught: '{log_pattern}'", symbol="✔")
                    # If no probe command, we're done
                    if not probe_cmd: return True
                    # Otherwise, continue to probe check
            except:
                pass

        # Signal 2: Network/Probe Command
        if probe_cmd:
            try:
                # Prefix with docker exec if it's not already
                full_cmd = ["docker", "exec", container_name] + probe_cmd
                probe_res = subprocess.run(full_cmd, capture_output=True, shell=use_shell, env=GLOBAL_ENV)
                if probe_res.returncode == 0:
                    t_log(f"{name} network probe SUCCEEDED.", symbol="✔")
                    return True
            except:
                pass
        
        # If neither signal hit but container is running, we wait
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
        import bcrypt
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
        dot_env = REPO_ROOT / ".env"
        has_dotenv = dot_env.exists()
        
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
        use_shell = os.name == "nt"
        try:
            retry(lambda: subprocess.run(["docker", "network", "create", "proxy"], 
                                       capture_output=True, shell=use_shell, env=GLOBAL_ENV, check=True))
            t_log("[DOCKER] Shared network 'proxy' ready")
        except: pass 
        
        # Shared UI State
        global_live_list = LiveList([])
        active_stacks = [] # List of (stack_name, path, is_critical, total_svc, expected_services_list)
        stop_poller = threading.Event()

        def ui_status_poller():
            """Continuously updates the GlobalLiveList for all active stacks."""
            while not stop_poller.is_set():
                for name, sd, is_critical, total, services in list(active_stacks):
                    cf = sd / "docker-compose.yml"
                    ps_res = subprocess.run(["docker", "compose", "-f", str(cf), "ps", "--format", "json"],
                                         capture_output=True, text=True, shell=use_shell, env=GLOBAL_ENV)
                    if ps_res.returncode == 0:
                        out = ps_res.stdout.strip()
                        ps_data = []
                        try:
                            if out.startswith("["): ps_data = json.loads(out)
                            elif out: ps_data = [json.loads(l) for l in out.splitlines()]
                        except: pass
                        
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
                                
                                global_live_list.update(item, smart_state)
                            else:
                                pass
                time.sleep(2)

        poller_thread = threading.Thread(target=ui_status_poller, daemon=True)
        poller_thread.start()

        stacks = [
            ("routing", REPO_ROOT / "docker" / "routing", True),    # CRITICAL: Gateway
            ("network", REPO_ROOT / "docker" / "network", True),    # CRITICAL: VPN
            ("maintenance", REPO_ROOT / "docker" / "maintenance", False),
            ("core", REPO_ROOT / "docker" / "core", True),         # CRITICAL: Agents/Dashboard
            ("media", REPO_ROOT / "docker" / "media", False),
            ("apps/tattoo-app", REPO_ROOT / "docker" / "apps" / "tattoo-app", False)
        ]
        
        # Tiered Timeouts
        TIMEOUTS = {
            "routing": 90,
            "network": 90,
            "core": 60,
            "media": 120,
            "apps/tattoo-app": 60
        }

        # Readiness definitions (Log Pattern, Probe Command)
        READINESS = {
            "routing": ("cloudflared", "Registered tunnel connection", ["curl", "-s", "-f", "https://ipinfo.io"]),
            "network": ("gluetun", "VPN is up", ["curl", "-s", "-f", "https://ifconfig.me"]),
            "core": ("m3tal-dashboard", None, ["curl", "-s", "-f", "http://localhost:8080/api/health"])
        }
        
        for name, sd, is_critical in stacks:
            cf = sd / "docker-compose.yml"
            if not cf.exists(): continue
            
            t_log(f"[DOCKER] Orchestrating stack: {name}")
            
            # Sub-item: Detect expected services
            conf_cmd = ["docker", "compose", "-f", str(cf), "config", "--services"]
            conf_res = subprocess.run(conf_cmd, capture_output=True, text=True, shell=use_shell, env=GLOBAL_ENV)
            expected_services = conf_res.stdout.strip().splitlines() if conf_res.returncode == 0 else []
            total_svc = len(expected_services)
            
            sub_bar = SubProgressBar(total_svc)
            live_list = LiveList(expected_services)
            sub_bar.update(0, f"Initializing {total_svc} services ({name})")

            try:
                # 1. Register stack and start launch
                active_stacks.append((name, sd, is_critical, total_svc, expected_services))
                global_live_list.add_items(expected_services)
                
                proc = subprocess.Popen(["docker", "compose", "-f", str(cf), "up", "-d"], 
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                                     text=True, shell=use_shell, env=GLOBAL_ENV)
                
                # 2. Wait for Docker status (Up/Running)
                wait_time = TIMEOUTS.get(name, 90)
                start_time = time.time()
                while time.time() - start_time < wait_time:
                    if proc.poll() is not None and proc.returncode != 0:
                        raise RuntimeError(f"Docker Launch Error (Exit {proc.returncode}) for {name}")
                    
                    ready_count = sum(1 for item in expected_services 
                                    if global_live_list.statuses.get(item) in ["running", "healthy", "done"])
                    
                    sub_bar.update(ready_count, f"Processed {ready_count}/{total_svc} ({name})")
                    if ready_count >= total_svc: break
                    
                    if ready_count == 0 and proc.poll() is None:
                        for item in expected_services:
                            if global_live_list.statuses.get(item) == "queued":
                                global_live_list.update(item, "pulling")
                    time.sleep(1.5)

                # 3. Enhanced Readiness Check (Multi-Signal)
                if name in READINESS:
                    c_name, l_pat, p_cmd = READINESS[name]
                    if not wait_for_readiness(name, c_name, l_pat, p_cmd, timeout=wait_time):
                        if is_critical:
                            raise RuntimeError(f"Critical service {c_name} in {name} stack failed readiness probes.")

                if ready_count < total_svc:
                    if is_critical:
                        t_log(f"[DOCKER] Stack {name} timed out. Proceeding in DEGRADED mode.", symbol="⚠")
                        update_status("docker", "partial")
                    else:
                        t_log(f"[DOCKER] Stack {name} launched in background. Moving on.", symbol="🚀")
                
                # Lock the lines
                live_list.reset()
                
            except Exception as e:
                t_log(f"[DOCKER] Stack {name} failed: {e}", symbol="⚠")
                update_status("docker", "partial")
                if 'live_list' in locals(): live_list.reset()
        
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
        stacks_to_fix = [scope] if scope != "all" else ["routing", "maintenance", "core", "media", "apps/tattoo-app"]
        for stack in stacks_to_fix:
            sd = REPO_ROOT / "docker" / stack
            if not sd.exists(): continue
            t_log(f"[REPAIR] Rebuilding {stack} stack...", symbol="🔧")
            subprocess.run(["docker", "compose", "up", "-d", "--force-recreate"], 
                         cwd=str(sd), shell=(os.name=="nt"), env=GLOBAL_ENV, capture_output=True)
        return True
    except Exception as e:
        t_log(f"Repair failed: {e}", symbol="✘")
        return False

# --- Main Orchestrator --------------------------------------------------------

def run_init(repair_scope: str = None) -> bool:
    """Main entry point: Orchestrates the entire bootstrap with preflight guarding."""
    repair_mode = bool(repair_scope)
    Header.show("M3TAL Self-Healing Init", f"Production Bootstrap — Repair: {repair_scope or 'None'}")
    
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
        if not fs_agent(repair_mode=(repair_scope in ["all", "fs"])):
            return False
            
        # Step 2: Logs
        BAR.update(3, "Logs")
        log_agent(repair_mode=(repair_scope in ["all", "logs"]))
        
        # Step 3: State
        BAR.update(4, "State")
        if not state_agent(repair_mode=(repair_scope in ["all", "state"])):
            return False
            
        # Step 4: Auth
        BAR.update(5, "Auth")
        auth_agent()
        
        # Step 5: Docker
        BAR.update(6, "Docker")
        docker_agent(repair_mode=(repair_scope == "all"))
        
        # Step 6: Final Health
        BAR.update(7, "Health")
        ready = health_agent()
        BAR.update(8, "Cleanup")
        
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
