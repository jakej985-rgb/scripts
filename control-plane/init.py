#!/usr/bin/env python3
"""
M3TAL Control Plane — State Scaffolding & Self-Healing Init
v1.3.0 — Cross-platform Python replacement for init.sh

Ensures all required directories, log files, state files, and auth
scaffolding exist and are valid. Idempotent — safe to run repeatedly.
"""

import json
import os
import stat
import sys
from pathlib import Path

# --- Context Anchoring --------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent

# Add support directories to system path for local imports
for path in [REPO_ROOT / "scripts", REPO_ROOT / "dashboard"]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from validate_env import validate_env, load_env
    from validate_images import validate_images
    from progress_utils import (
        log_step, Heartbeat, Spinner, ProgressBar,
        BOLD, END, BLUE, CYAN, DIM, GREEN, RED, YELLOW
    )
except ImportError:
    validate_env = None
    load_env = None
    validate_images = None
    log_step = lambda s, t, m: print(f"[{s}/{t}] {m}")
    Heartbeat = None
    Spinner = None

from auth import inspect_users_file, reset_admin_user, resolve_users_path

# --- Path System --------------------------------------------------------------
STATE_DIR = BASE_DIR / "state"
LOG_DIR = STATE_DIR / "logs"
LOCK_DIR = STATE_DIR / "locks"
HEALTH_DIR = STATE_DIR / "health"
TMP_DIR = STATE_DIR / "tmp"
AGENTS_DIR = BASE_DIR / "agents"
DASHBOARD_DIR = REPO_ROOT / "dashboard"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCKER_DIR = REPO_ROOT / "docker" / "media"
DOCKER_ROOT = REPO_ROOT / "docker"

# --- Compose Stacks (launch order matters) ------------------------------------
COMPOSE_STACKS = [
    ("routing",     DOCKER_ROOT / "routing"),
    ("core",        DOCKER_ROOT / "core"),
    ("media",       DOCKER_ROOT / "media"),
    ("maintenance", DOCKER_ROOT / "maintenance"),
]

# --- Directory tree -----------------------------------------------------------
REQUIRED_DIRS = [
    STATE_DIR,
    LOG_DIR,
    LOCK_DIR,
    HEALTH_DIR,
    TMP_DIR,
    AGENTS_DIR,
    DOCKER_DIR,
    SCRIPTS_DIR,
]

# --- Log files ---------------------------------------------------------------

REQUIRED_LOGS = [
    "monitor.log",
    "metrics.log",
    "anomaly.log",
    "decision.log",
    "reconcile.log",
    "registry.log",
    "observer.log",
    "scorer.log",
    "chaos.log",
    "supervisor.log",
]

# --- State files (JSON) ------------------------------------------------------

STATE_FILE_DEFAULTS = {
    "metrics.json": {"system": {}, "containers": [], "timestamp": 0, "cpu": 0},
    "normalized_metrics.json": {},
    "anomalies.json": {"issues": []},
    "decisions.json": {"actions": []},
    "registry.json": {"containers": []},
    "health.json": {},
    "health_report.json": {},
    "chaos_events.json": [],
    "cooldowns.json": {},
    "scaling_actions.json": {"actions": []},
    "scaling_cooldowns.json": {},
    "last_prune.json": {"ts": 0},
}


def log(msg):
    """Centralized logger that is heartbeat-aware to prevent terminal collisions."""
    hb = globals().get('CURRENT_HB')
    if hb:
        hb.log(f"{BOLD}[INIT]{END} {msg}")
    else:
        print(f"{BOLD}[INIT]{END} {msg}")

def log_step(step: int, total: int, message: str, bar=None):
    prefix = f"{BLUE}{BOLD}[INIT] Step {step}/{total}:{END}"
    if hb := globals().get('CURRENT_HB'):
        hb.log(f"\n{prefix} {message}")
    else:
        print(f"\n{prefix} {message}")
    
    if bar:
        bar.update(step, message)

def scaffold_dirs() -> None:
    """Create all required directories if they don't exist."""
    for d in REQUIRED_DIRS:
        if not d.exists():
            log(f"Creating missing dir: {d}")
            d.mkdir(parents=True, exist_ok=True)


def scaffold_logs() -> None:
    """Touch all required log files."""
    for name in REQUIRED_LOGS:
        path = LOG_DIR / name
        if not path.exists():
            log(f"Creating missing log: {name}")
            path.touch()


def write_state_default(path: Path, default_data: object) -> None:
    path.write_text(f"{json.dumps(default_data, indent=2)}\n", encoding="utf-8")


def scaffold_state_files() -> None:
    """Ensure state JSON files exist and are valid JSON with agent-safe defaults."""
    for name, default_data in STATE_FILE_DEFAULTS.items():
        path = STATE_DIR / name
        if not path.exists():
            write_state_default(path, default_data)
            log(f"Recreated {name}")
        else:
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                write_state_default(path, default_data)
                log(f"Reset corrupted {name}")

    # leader.txt — always ensure it exists and has a baseline
    leader_path = STATE_DIR / "leader.txt"
    if not leader_path.exists() or leader_path.stat().st_size == 0:
        leader_path.write_text("none\n", encoding="utf-8")
        log("Initialized leader.txt with 'none'")


def scaffold_users(interactive: bool | None = None, allow_missing: bool = False) -> None:
    """Ensure dashboard credentials exist without recreating insecure defaults."""
    users_path = resolve_users_path(DASHBOARD_DIR)
    _, error = inspect_users_file(users_path=users_path)
    if error is None:
        return

    # In CI environments or dry-runs, we skip the fatal error to allow automation
    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    if allow_missing or is_ci:
        log(f"Headless/CI session detected: Skipping mandatory admin setup ({error}).")
        return

    if interactive is None:
        interactive = sys.stdin.isatty()

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    if not interactive:
        raise RuntimeError(
            f"Dashboard admin is not configured ({error}). "
            "Run `python scripts/manage_users.py --reset-admin` from an interactive terminal."
        )

    log(f"Dashboard users file is {error}. Starting interactive admin setup...")
    reset_admin_user(users_path=users_path)
    log(f"Created {users_path.name} with a newly prompted admin password.")


def harden_permissions() -> None:
    """Set restrictive permissions on the state directory (Unix only)."""
    if sys.platform == "win32":
        return  # chmod is not meaningful on Windows
    try:
        # Step through all files/dirs in STATE_DIR
        for path in STATE_DIR.rglob("*"):
            if path.is_dir():
                path.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
            else:
                path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    except Exception:
        pass  # Best-effort; non-fatal


# --- Execution ----------------------------------------------------------------
import subprocess


def launch_compose_stacks(hb=None) -> None:
    """Bring up all Docker Compose stacks in dependency order."""
    env_file = REPO_ROOT / ".env"
    use_shell = os.name == "nt"

    # Ensure the shared Docker network exists
    try:
        subprocess.run(
            ["docker", "network", "create", "m3tal"],
            capture_output=True, shell=use_shell
        )
    except Exception:
        pass  # Network may already exist

    # Initialize a sub-progress bar for the stacks
    stack_count = len(COMPOSE_STACKS)
    stack_bar = ProgressBar(stack_count, prefix="  Stacks", width=20)

    for i, (stack_name, stack_dir) in enumerate(COMPOSE_STACKS, 1):
        compose_file = stack_dir / "docker-compose.yml"
        if not compose_file.exists():
            log(f"  Skipping {stack_name}: no docker-compose.yml found")
            continue

        if hb: hb.ping(f"Launching {stack_name}")
        stack_bar.update(i - 1, f"Starting {stack_name}...")
        
        cmd = [
            "docker", "compose",
            "-f", str(compose_file),
            "--env-file", str(env_file),
            "up", "-d", "--remove-orphans"
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=use_shell,
                timeout=180 # Increased timeout for heavy maintenance stacks
            )
            if result.returncode == 0:
                log(f"  ✅ {stack_name} — UP")
                if hb: hb.ping(f"{stack_name} ready")
                stack_bar.update(i, f"Finished {stack_name}")
            else:
                stderr_snippet = (result.stderr or "").strip()[:200]
                log(f"  ⚠️  {stack_name} — WARNING: {stderr_snippet}")
                stack_bar.update(i, f"Partial {stack_name}")
        except subprocess.TimeoutExpired:
            log(f"  ⚠️  {stack_name} — TIMEOUT after 180s")
            stack_bar.update(i, f"Timeout {stack_name}")
        except Exception as e:
            log(f"  ⚠️  {stack_name} — ERROR: {e}")
            stack_bar.update(i, f"Error {stack_name}")

def run(dry_run: bool = False, interactive: bool | None = None) -> None:
    """Core Orchestrator: filesystem → env → image → validation → startup"""
    
    # 0. Recursion Guard
    if os.environ.get("INIT_ALREADY_RUN") == "1":
        return
    os.environ["INIT_ALREADY_RUN"] = "1"

    log("Starting M3TAL Self-Healing Orchestrator...")
    
    # Pre-flight: Autonomous Env Injection
    if load_env:
        load_env()
    
    # 0.1 Heartbeat System
    hb = Heartbeat() if 'Heartbeat' in globals() and Heartbeat else None
    globals()['CURRENT_HB'] = hb
    if hb: hb.start()

    # Initialize persistent progress bar as per USER Request
    main_bar = ProgressBar(9, prefix=f"{BOLD}[INIT]{END}")

    try:
        # 0.2 Context Debug
        log(f"DEBUG: CWD = {os.getcwd()}")
        log(f"DEBUG: BASE_DIR = {BASE_DIR}")
        
        # 0.3 Context Validation
        if not DOCKER_DIR.exists():
            log(f"FATAL: Docker directory missing: {DOCKER_DIR}")
            sys.exit(1)

        # Step 1: Filesystem
        if hb: hb.ping("Initializing directories")
        log_step(1, 9, "Initializing system directories", bar=main_bar)
        scaffold_dirs()
        
        # Step 2: Critical Scaffolding
        if hb: hb.ping("Scaffolding state")
        log_step(2, 9, "Scaffolding state files and identity baseline", bar=main_bar)
        scaffold_logs()
        scaffold_state_files()
        scaffold_users(interactive=interactive, allow_missing=dry_run)
        if not dry_run:
            harden_permissions()

        # Step 3: Environment Audit
        if hb: hb.ping("Auditing environment")
        log_step(3, 9, "Auditing environment integrity", bar=main_bar)
        if validate_env:
            valid, _ = validate_env(interactive=True)
            if not valid:
                log("Core environment missing. Run 'python scripts/configure_env.py' to fix.")
                sys.exit(1)

        # Step 4: Environment Context
        if hb: hb.ping("Environment context")
        log_step(4, 9, "Standardizing environment context", bar=main_bar)

        # Step 5: Image Audit
        if hb: hb.ping("Scanning Docker images")
        log_step(5, 9, "Auditing Docker image availability", bar=main_bar)
        if validate_images:
            all_ok = validate_images(pull=False)
            
            # Step 6: Image Repair (Stage 2)
            if hb: hb.ping("Image repair")
            log_step(6, 9, "Autonomous image repair and correction", bar=main_bar)
            if not all_ok:
                log("Image issues detected. Attempting autonomous repair...")
                repair_ok = validate_images(pull=True, fix=True)
                if not repair_ok:
                    log("FATAL: Image validation failed after autonomous repair attempt.")
                    sys.exit(1)
                log("Image repair complete.")
            else:
                log("No image repairs required.")

            # Step 7: Final Enforcement
            if hb: hb.ping("Final verification")
            log_step(7, 9, "Final infrastructure enforcement", bar=main_bar)
            if not validate_images(pull=False):
                log("FATAL: Final image verification failed.")
                sys.exit(1)

        log("Image validation complete.")

        # Step 8: Launch Docker Compose Stacks
        if not dry_run:
            if hb: hb.ping("Launching compose stacks")
            log_step(8, 9, "Launching Docker Compose stacks", bar=main_bar)
            launch_compose_stacks(hb=hb)
        else:
            log_step(8, 9, "Skipping stack launch (dry-run)", bar=main_bar)

        log("System initialization complete.")
    
        # Step 9: Startup Hand-off
        if "--start" in sys.argv:
            if hb: hb.ping("Handing off to supervisor")
            log_step(9, 9, "Supervisor hand-off", bar=main_bar)
            log("Handing off control to supervisor.py...")
            try:
                supervisor_script = BASE_DIR / "supervisor.py"
                subprocess.run([sys.executable, str(supervisor_script)], check=True)
            except KeyboardInterrupt:
                log("Supervisor terminated by user.")
            except Exception as e:
                log(f"Supervisor failed: {e}")
                sys.exit(1)
        else:
            log_step(9, 9, "Ready for manual startup", bar=main_bar)

    finally:
        if hb: hb.stop()

def run_cli():
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)

if __name__ == "__main__":
    run_cli()
