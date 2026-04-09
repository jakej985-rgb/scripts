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
BASE_DIR = REPO_ROOT
STATE_DIR = BASE_DIR / "control-plane" / "state"
LOG_DIR = STATE_DIR / "logs"
LOCK_DIR = STATE_DIR / "locks"
HEALTH_DIR = STATE_DIR / "health"
TMP_DIR = STATE_DIR / "tmp"
AGENTS_DIR = BASE_DIR / "control-plane" / "agents"
DASHBOARD_DIR = BASE_DIR / "dashboard"

# --- Directory tree -----------------------------------------------------------

REQUIRED_DIRS = [
    STATE_DIR,
    LOG_DIR,
    LOCK_DIR,
    HEALTH_DIR,
    TMP_DIR,
    AGENTS_DIR,
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

# --- State files (JSON) — reset to [] if missing or corrupted ----------------

STATE_FILES = [
    "metrics.json",
    "normalized_metrics.json",
    "anomalies.json",
    "decisions.json",
    "registry.json",
    "health.json",
    "chaos_events.json",
    "cooldowns.json",
]

# --- Default admin user scaffold ---------------------------------------------

DEFAULT_USERS = [
    {
        "username": "admin",
        "token_hash": "$2b$12$6PuxP6N7ZpG5B9W7/p3E.e3u0Xm6x6u1vXm6x6u1vXm6x6u1vXm6x6u1v",
        "role": "admin",
    }
]


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


def scaffold_state_files() -> None:
    """Ensure state JSON files exist and are valid JSON.
    If missing → create with [].
    If corrupted → reset to [].
    """
    for name in STATE_FILES:
        path = STATE_DIR / name
        if not path.exists():
            path.write_text("[]")
            log(f"Recreated {name}")
        else:
            try:
                json.loads(path.read_text())
            except (json.JSONDecodeError, ValueError):
                path.write_text("[]")
                log(f"Reset corrupted {name}")

    # leader.txt — always ensure it exists
    leader_path = STATE_DIR / "leader.txt"
    if not leader_path.exists():
        leader_path.touch()
        log("Created leader.txt")


def scaffold_users() -> None:
    """Create default dashboard users.json if it doesn't exist."""
    users_path = DASHBOARD_DIR / "users.json"
    if not users_path.exists():
        log("Scaffolding default users.json (admin / admin123)...")
        DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
        users_path.write_text(json.dumps(DEFAULT_USERS, indent=2))


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


def run(dry_run: bool = False) -> None:
    """Execute the full init sequence."""
    log("Running self-healing setup...")
    scaffold_dirs()
    scaffold_logs()
    scaffold_state_files()
    scaffold_users()
    if not dry_run:
        harden_permissions()
    log("Done.")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
