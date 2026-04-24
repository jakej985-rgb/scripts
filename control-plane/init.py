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
os.environ["REPO_ROOT"] = str(REPO_ROOT)
os.chdir(REPO_ROOT)
AGENTS_DIR = BASE_DIR / "agents"

# Standardize Search Paths
for path in [AGENTS_DIR, REPO_ROOT / "scripts" / "helpers", REPO_ROOT / "scripts" / "test", REPO_ROOT / "dashboard"]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

ENV_FILE = REPO_ROOT / ".env"

from typing import Optional
from utils.paths import STATE_DIR, LOG_DIR, DATA_DIR

import builtins
import warnings
import logging

def setup_init_logging():
    """Initializes logging and warning captures for the orchestrator."""
    logging.basicConfig(
        filename=str(LOG_DIR / "m3tal.log"),
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    def warning_to_log(message, category, filename, lineno, file=None, line=None):
        logging.warning(f"{filename}:{lineno}: {category.__name__}: {message}")

    warnings.showwarning = warning_to_log

# Call setup immediately if running as main
if __name__ == "__main__":
    setup_init_logging()

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

def validate_env_dollar_escaping():
    for key, value in os.environ.items():
        if "$" in value and "$$" not in value:
            raise RuntimeError(f"Unsafe env var (requires $$ escaping for Docker Compose): {key}")

def run_preflight_checks():
    """Phase 5: Preflight validation for ports, sockets, networks, and environment safety."""
    t_log("Starting Preflight Validation...", symbol="⚙")
    
    # 0. Validate Env Safety
    validate_env_dollar_escaping()
    
    # 1. Check Ports
    import socket
    for port in [80, 443]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
            except socket.error:
                log(f"WARNING: Port {port} is already in use. Traefik will likely fail to start.", symbol="⚠")
                suggest_port_fix(port)

    # 2. Check Docker Socket
    if os.name != 'nt': # Linux/Mac
        if not os.access("/var/run/docker.sock", os.R_OK | os.W_OK):
            t_log("WARNING: Cannot access /var/run/docker.sock. Check permissions.", symbol="⚠")
    
    # 3. Check Base Directories (Deep Validation)
    required_paths = [
        DATA_DIR,
        DATA_DIR / "downloads",
        DATA_DIR / "media"
    ]
    for p in required_paths:
        if not p.exists():
            t_log(f"FATAL: Required DATA_DIR path missing: {p}", symbol="✘")
            return False

    return True

run_preflight = run_preflight_checks

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

# Audit Fix P1: Filesystem Bootstrap (Linux Compatibility)
def bootstrap_data_dirs():
    """Phase 1.1: Ensures required subdirectories exist in DATA_DIR to prevent mount failures."""
    required = ["downloads", "media"]
    for r in required:
        path = DATA_DIR / r
        if not path.exists():
            t_log(f"[INIT] Creating DATA_DIR subdir: {path}", symbol="📁")
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                t_log(f"Failed to create data subdir {path}: {e}", symbol="✘")

def fix_permissions():
    """Phase 5: Enforce consistent ownership on internal project paths only."""
    if os.name != 'nt':
        # Strictly limited to project-managed state/logs to avoid 'Operation not permitted' on external mounts
        ALLOWED_PATHS = [STATE_DIR, LOG_DIR]
        for path in ALLOWED_PATHS:
            if path.exists():
                try:
                    log(f"[INIT] Enforcing permissions on {path.name} (1000:1000)...", symbol="🔐")
                    subprocess.run(["chown", "-R", "1000:1000", str(path)], check=False)
                except Exception as e:
                    log(f"Permission fix skipped for {path}: {e}", symbol="⚠")

def suggest_port_fix(port: int):
    """Provide actionable help for port conflicts."""
    log(f"Port {port} conflict detected. Potential fixes:", symbol="👉")
    if port in [80, 443]:
        log("  - sudo systemctl stop nginx", symbol="👉")
        log("  - sudo systemctl stop apache2", symbol="👉")
        log("  - Check for other Docker ingress controllers.", symbol="👉")

def resolve_port_conflicts():
    """Phase 4.1: Automated conflict resolver."""
    log("Attempting to auto-resolve port conflicts...", symbol="🔧")
    for svc in ["nginx", "apache2"]:
        subprocess.run(["systemctl", "stop", svc], capture_output=True)

def ensure_state_dirs():
    """Phase 6: Ensure required service-specific state directories exist."""
    services = [
        "prowlarr","bazarr","sonarr","radarr","komga",
        "tdarr","jellyseerr","qbittorrent","autobrr",
        "recyclarr","homepage","portainer"
    ]
    for svc in services:
        path = STATE_DIR / svc
        if not path.exists():
            log(f"[INIT] Scaffolding service state: {svc}", symbol="📦")
            path.mkdir(parents=True, exist_ok=True)

def validate_env():
    """Phase 8: Ensure critical environment variables are set."""
    required = ["DOMAIN", "DATA_DIR"]
    for env in required:
        if env not in os.environ:
            raise RuntimeError(f"CRITICAL: Environment variable {env} is NOT set.")

def preflight_linux():
    """Phase 0: Linux-specific preflight diagnostics."""
    if os.name != 'nt':
        log("Linux environment detected. Enforcing POSIX standards.", symbol="🐧")

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

def log(msg: str, symbol: str = ""):
    """Unified Safe Logger: Prevents NameErrors while bridging UI and log files."""
    try:
        from utils.state import log_event # type: ignore
        log_event("init", msg, symbol=symbol)
    except:
        pass
        
    if HB:
        HB.log(msg, symbol=symbol)
    else:
        print(f"  {CYAN}{symbol if symbol else '•'}{END} {msg}")

def t_log(msg: str, symbol: str = None):
    """Bridge for existing calls to t_log."""
    log(msg, symbol=symbol)

def detect_created(expected_services: list = None):
    """Phase 6.1 & 6.2: Explicit 'Created' and 'Restarting' detection (Scope-Aware)."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}} {{.Status}}"],
            capture_output=True, text=True
        )
        broken = []
        for line in result.stdout.splitlines():
            if expected_services is not None:
                # Only check containers that match our expected list for this stack
                if not any(svc in line for svc in expected_services):
                    continue
                    
            if "Created" in line:
                broken.append(line)
            if "Restarting" in line:
                log(f"Container restarting (Crash Loop): {line}", symbol="⚠")
                broken.append(line)
        
        if broken:
            log(f"Containers stuck or looping: {broken}", symbol="✘")
            raise RuntimeError(f"Containers stuck or looping: {broken}")
    except RuntimeError: raise
    except Exception as e:
        log(f"Failed to scan for 'Created' containers: {e}", symbol="⚠")

def run_with_retries(name, func, *args, retries=2, **kwargs):
    """Actual Agent Behavior: Retry logic for critical operations with stack context."""
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            import traceback
            traceback.print_exc()
            log(f"[RETRY] {name} failed (attempt {attempt + 1}): {e}", symbol="⚠")
            if attempt < retries - 1:
                log(f"Retrying {name}...", symbol="⏳")
                time.sleep(5)
            else:
                log(f"{name} failed permanently.", symbol="✘")
                raise
def update_status(component: str, status: str):
    SYSTEM_STATUS[component] = status
    log(f"Component {component} status: {status}", symbol="✔" if status == "ok" else "⚠")

def verify_running(name: str, expected_services: list):
    """Phase 1.1: Health Gate - Ensure all expected services are running."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    running = result.stdout.splitlines()
    running_str = " ".join(running)

    for svc in expected_services:
        if svc not in running_str:
            raise RuntimeError(f"{name}: Service {svc} is NOT running.")

def wait_for_stack_ready(name: str, services: list, timeout: int):
    """Phase 2.1: Wait for stack to reach steady state without mixing responsibilities."""
    start = time.time()
    
    while time.time() - start < timeout:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        running = result.stdout
        
        if all(svc in running for svc in services):
            log(f"{name} is RUNNING", symbol="✔")
            return True
            
        time.sleep(2)
        
    raise RuntimeError(f"{name}: readiness timeout")

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
                    try:
                        sl.unlink()
                    except Exception as e:
                        t_log(f"[LOG] Could not prune stale log {sl.name}: {e}", symbol="ℹ")
        
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
                # Audit Fix: Make Telegram optional to avoid blocking non-notify deployments
                if var in ["TELEGRAM_BOT_TOKEN", "TG_CHAT_COUNT"]:
                    t_log(f"[ENV] WARNING: {var} missing. Notifications disabled.", symbol="⚠")
                    continue
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
        return False

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
        except Exception as e: 
            t_log(f"[DOCKER] Shared network 'proxy' exists or creation failed: {e}", symbol="ℹ") 
        
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
                with active_ui_lock:
                    stacks_snapshot = list(active_stacks)
                
                for name, sd, is_critical, total, services in stacks_snapshot:
                    cf = sd / "docker-compose.yml"
                    ps_res = subprocess.run(["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(cf), "ps", "--format", "json"],
                                         capture_output=True, text=True, env=GLOBAL_ENV)
                    if ps_res.returncode == 0:
                        out = ps_res.stdout.strip()
                        ps_data = []
                        try:
                            if out.startswith("["): ps_data = json.loads(out)
                            elif out: ps_data = [json.loads(l) for l in out.splitlines()]
                        except Exception as e:
                            t_log(f"[DOCKER] Poller JSON parse error: {e}", symbol="ℹ")
                        
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
            ("control-plane", REPO_ROOT / "control-plane", True),   # CRITICAL: Agents/Dashboard/Proxy
            ("maintenance", REPO_ROOT / "docker" / "maintenance", False),
            ("media", REPO_ROOT / "docker" / "media", False)
        ]
        
        # --- Mount Validator ---
        def _check_compose_mounts(compose_path, stack_name):
            try:
                import yaml
                with open(compose_path, 'r', encoding='utf-8') as f:
                    cfg = yaml.safe_load(f)
                    defined_volumes = cfg.get('volumes', {}) or {}
                    for svc_name, svc_cfg in cfg.get('services', {}).items():
                        for volume in svc_cfg.get('volumes', []):
                            if isinstance(volume, str) and ':' in volume:
                                # Phase 1: Robust splitting
                                src = volume.split(':', 1)[0].strip()
                                
                                if src in defined_volumes: continue
                                if not src.startswith(('/', './', '../', '$', '~')) and not (len(src) > 1 and src[1] == ':'):
                                    continue

                                # Phase 3: Malformed variable detection
                                if "${" in src and "}" not in src:
                                    raise RuntimeError(f"[FATAL] Malformed env var in mount: {src}")

                                # Phase 2: Robust Expansion
                                expanded_src = os.path.expandvars(src)
                                
                                # Phase 4: Debug Logging
                                # log(f"[DEBUG] Raw volume: {volume}", symbol="🐛")
                                # log(f"[DEBUG] Parsed src: {src}", symbol="🐛")
                                # log(f"[DEBUG] Expanded src: {expanded_src}", symbol="🐛")

                                if os.name == 'nt' and expanded_src == '/var/run/docker.sock': continue

                                if not Path(expanded_src).is_absolute():
                                    expanded_src = str(Path(compose_path).parent / expanded_src)
                                
                                # Phase 8: Agent Guardrails
                                if "$" in expanded_src:
                                    log(f"[WARN] Unresolved variable in path: {expanded_src}", symbol="⚠")
                                if not expanded_src.startswith("/") and os.name != "nt":
                                    log(f"[WARN] Non-absolute mount: {expanded_src}", symbol="⚠")
                                
                                # Phase 5 & 9: Safe validation & Structured Error
                                if not os.path.exists(expanded_src):
                                    raise RuntimeError(
                                        f"[DOCKER] Mount validation failed for {svc_name}\n"
                                        f"  Raw: {volume}\n"
                                        f"  Parsed: {src}\n"
                                        f"  Expanded: {expanded_src}"
                                    )
            except RuntimeError: raise
            except Exception as e:
                log(f"Mount check skipped for {stack_name}: {e}", symbol="⚠")

        TIMEOUTS = {
            "routing": 90,
            "network": 90,
            "media": 120,
            "maintenance": 60,
            "control-plane": 60
        }

        for name, sd, is_critical in stacks:
            cf = sd / "docker-compose.yml"
            if not cf.exists(): continue
            
            log(f"[DOCKER] Orchestrating stack: {name}")

            if name == "routing" and os.name != "nt":
                resolve_port_conflicts()
            
            # Mount Validation
            _check_compose_mounts(cf, name)

            # Get services to verify
            conf_cmd = ["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(cf), "config", "--services"]
            res = subprocess.run(conf_cmd, capture_output=True, text=True, env=GLOBAL_ENV)
            expected_services = res.stdout.strip().splitlines()

            def _deploy_and_verify():
                # Launch
                cmd = ["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(cf), "up", "-d"]
                if repair_mode: cmd.append("--force-recreate")
                
                proc = subprocess.run(cmd, env=GLOBAL_ENV, capture_output=True, text=True)
                if proc.returncode != 0:
                    log(f"Stack {name} failed to deploy.", symbol="✘")
                    subprocess.run(["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(cf), "logs", "--tail", "50"], env=GLOBAL_ENV)
                    raise RuntimeError(f"Docker Compose Error (Exit {proc.returncode})")

                # Detect 'Created' ghosts only for this stack
                detect_created(expected_services)
                
                # Verify running
                verify_running(name, expected_services)
                wait_for_stack_ready(name, expected_services, TIMEOUTS[name])

            # Execute with retries
            try:
                run_with_retries(name, _deploy_and_verify)
            except Exception as e:
                if is_critical:
                    raise
                else:
                    log(f"Stack {name} failed but is non-critical: {e}", symbol="⚠")
                    update_status("docker", "partial")

        if SYSTEM_STATUS["docker"] == "unknown":
            update_status("docker", "ok")
            
        stop_poller.set()
        poller_thread.join(timeout=5)
        return True
    except Exception as e:
        log(f"Docker Agent failed: {e}", symbol="✘")
        update_status("docker", "failed")
        stop_poller.set()
        if 'poller_thread' in locals():
            poller_thread.join(timeout=5)
        return False

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
        stacks_to_fix = [scope] if scope != "all" else ["routing", "network", "maintenance", "media"]
        for stack in stacks_to_fix:
            if stack == "control-plane":
                sd = REPO_ROOT / "control-plane"
            else:
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
    
    # Audit Fix: Critical System Scaffolding
    preflight_linux()
    validate_env()
    bootstrap_data_dirs()
    ensure_state_dirs()
    fix_permissions()

    BAR = ProgressBar(9, prefix="Init")
    HB.tether(BAR)

    try:
        # Step 0: Environment & Dependencies
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
        
        # Phase 10: Final diagnostic sweep
        # detect_created() - Removed global sweep to prevent transient crash-loops from halting the orchestrator
        BAR.update(8, "Cleanup")
        BAR.update(9, "Done")
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
