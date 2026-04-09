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
# CORE: All internal paths derive from these two anchors
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent

# Add support directories to system path for local imports
for path in [REPO_ROOT / "scripts", REPO_ROOT / "dashboard"]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from validate_env import validate_env
    from validate_images import validate_images
    from progress_utils import log_step, Heartbeat, Spinner
except ImportError:
    validate_env = None
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
DOCKER_MEDIA_DIR = REPO_ROOT / "docker" / "media"

# --- Directory tree -----------------------------------------------------------

REQUIRED_DIRS = [
    STATE_DIR,
    LOG_DIR,
    LOCK_DIR,
    HEALTH_DIR,
    TMP_DIR,
    AGENTS_DIR,
    BASE_DIR / "docker" / "media",
    BASE_DIR / "scripts",
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


def log(msg: str) -> None:
    print(f"[INIT] {msg}")


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


def scaffold_users(interactive: bool | None = None) -> None:
    """Ensure dashboard credentials exist without recreating insecure defaults."""
    users_path = resolve_users_path(DASHBOARD_DIR)
    _, error = inspect_users_file(users_path=users_path)
    if error is None:
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
        for root, dirs, files in os.walk(STATE_DIR):
            for d in dirs:
                os.chmod(os.path.join(root, d), stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
            for f in files:
                os.chmod(os.path.join(root, f), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    except OSError:
        pass  # Best-effort; non-fatal


# --- Directory tree -----------------------------------------------------------

REQUIRED_DIRS = [
    STATE_DIR,
    LOG_DIR,
    LOCK_DIR,
    HEALTH_DIR,
    TMP_DIR,
    AGENTS_DIR,
    DOCKER_MEDIA_DIR,
    SCRIPTS_DIR,
]
import subprocess

def run(dry_run: bool = False, interactive: bool | None = None) -> None:
    """Core Orchestrator: filesystem → env → image → validation → startup"""
    
    # 0. Recursion Guard
    if os.environ.get("INIT_ALREADY_RUN") == "1":
        return
    os.environ["INIT_ALREADY_RUN"] = "1"

    log("🚀 Starting M3TAL Self-Healing Orchestrator...")
    
    # 0.1 Heartbeat System
    hb = Heartbeat() if 'Heartbeat' in globals() and Heartbeat else None
    if hb: hb.start()

    try:
        # 0.2 Context Debug
        log(f"DEBUG: CWD = {os.getcwd()}")
        log(f"DEBUG: BASE_DIR = {BASE_DIR}")
        
        # 0.3 Context Validation
        if not DOCKER_DIR.exists():
            log(f"FATAL: Docker directory missing: {DOCKER_DIR}")
            sys.exit(1)

        # Step 1: Filesystem
        log_step(1, 8, "Initializing system directories")
        scaffold_dirs()
        
        # Step 2: Critical Scaffolding
        log_step(2, 8, "Scaffolding state files and identity baseline")
        scaffold_logs()
        scaffold_state_files()
        scaffold_users(interactive=interactive)
        if not dry_run:
            harden_permissions()

        # Step 3: Environment Audit
        log_step(3, 8, "Auditing environment integrity")
        if validate_env:
            valid, _ = validate_env(interactive=True)
            if not valid:
                log("Core environment missing. Run 'python scripts/configure_env.py' to fix.")
                sys.exit(1)

        # Step 4: Environment Context
        log_step(4, 8, "Standardizing environment context")

        # Step 5: Image Audit
        log_step(5, 8, "Auditing Docker image availability")
        if validate_images:
            all_ok = validate_images(pull=False)
            
            # Step 6: Image Repair (Stage 2)
            log_step(6, 8, "Autonomous image repair and correction")
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
            log_step(7, 8, "Final infrastructure enforcement")
            if not validate_images(pull=False):
                log("FATAL: Final image verification failed.")
                sys.exit(1)

        log("✨ System initialization complete.")
    
        # Step 8: Startup Hand-off
        if "--start" in sys.argv:
            log_step(8, 8, "Supervisor hand-off")
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
            log_step(8, 8, "Ready for manual startup")

    finally:
        if hb: hb.stop()

def run_cli():
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)

if __name__ == "__main__":
    run_cli()
