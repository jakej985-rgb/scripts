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

# Resolve repo root: 2 levels up from control-plane/init.py
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "scripts"))
try:
    from validate_env import validate_env
    from validate_images import validate_images
except ImportError:
    validate_env = None
    validate_images = None

BASE_DIR = REPO_ROOT
STATE_DIR = BASE_DIR / "control-plane" / "state"
LOG_DIR = STATE_DIR / "logs"
LOCK_DIR = STATE_DIR / "locks"
HEALTH_DIR = STATE_DIR / "health"
TMP_DIR = STATE_DIR / "tmp"
AGENTS_DIR = BASE_DIR / "control-plane" / "agents"
DASHBOARD_DIR = BASE_DIR / "dashboard"

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from auth import inspect_users_file, reset_admin_user, resolve_users_path

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


import subprocess

def run(dry_run: bool = False, interactive: bool | None = None) -> None:
    """Core Orchestrator: filesystem → env → image → validation → startup"""
    log("🚀 Starting M3TAL Self-Healing Orchestrator...")
    
    # 1-2. Scaffolding (Filesystem + Files)
    scaffold_dirs()
    scaffold_logs()
    scaffold_state_files()
    scaffold_users(interactive=interactive)
    if not dry_run:
        harden_permissions()

    # 3-4. Env Preflight
    if validate_env:
        log("Checking environment integrity...")
        valid, missing = validate_env(interactive=True)
        if not valid:
            log("Core environment missing. Run 'python scripts/configure_env.py' to fix.")
            sys.exit(1)

    # 5. Image Validation (Stage 1: Non-blocking Audit)
    if validate_images:
        log("Stage 1: Auditing Docker images...")
        all_ok = validate_images(pull=False)
        
        # 6. Image Auto-Fix (Stage 2: pulls + repairs if needed)
        if not all_ok:
            log("Image issues detected. Attempting autonomous repair...")
            # Automatically try to repair (pull=True, fix=True)
            repair_ok = validate_images(pull=True, fix=True)
            
            # 7. Final Image Validation (Stage 3: Blocking)
            if not repair_ok:
                log("FATAL: Image validation failed after autonomous repair attempt.")
                sys.exit(1)
            log("Image repair complete.")
        else:
            log("All images verified.")

    log("✨ System initialization complete.")
    
    # 8. Start System (Optional Hand-off)
    if "--start" in sys.argv:
        log("Handing off control to supervisor.py...")
        try:
            # We use subprocess.run so we can see the supervisor output
            supervisor_script = BASE_DIR / "control-plane" / "supervisor.py"
            subprocess.run([sys.executable, str(supervisor_script)], check=True)
        except KeyboardInterrupt:
            log("Supervisor terminated by user.")
        except Exception as e:
            log(f"Supervisor failed: {e}")
            sys.exit(1)

def run_cli():
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)

if __name__ == "__main__":
    run_cli()
