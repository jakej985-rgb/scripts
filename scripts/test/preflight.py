#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

# --- Configuration ------------------------------------------------------------
MNT_POINT = "/mnt"
REQUIRED_ENV = ["DOMAIN"]
OPTIONAL_ENV = ["CF_TUNNEL_TOKEN"]

import shutil

# Load .env for manual testing
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                # Strip quotes/whitespace if present
                val = val.strip().strip('"').strip("'")
                os.environ[key.strip()] = val

def check_mount() -> bool:
    """Hard Check: Verify DATA_DIR is accessible and optionally verify capacity."""
    data_dir = os.getenv("DATA_DIR")
    if not data_dir:
        print("[X] CRITICAL: DATA_DIR environment variable is not defined.")
        return False
        
    path = Path(data_dir)
    
    # Windows Check: Linux paths like /mnt are invalid
    if os.name == "nt" and data_dir.startswith("/") and not data_dir.startswith("//"):
        print(f"[X] CRITICAL: Invalid Windows path detected: '{data_dir}'. Use a drive letter (e.g., D:).")
        return False

    if not path.exists():
        print(f"[!] WARNING: DATA_DIR path does not exist. Attempting to create: {path}")
        try:
            path.mkdir(parents=True, exist_ok=True)
            print(f"[OK] DATA_DIR created successfully.")
        except Exception as e:
            print(f"[X] CRITICAL: Failed to create DATA_DIR at {path}: {e}")
            return False
    
    # Informational: Empty check
    try:
        if not os.listdir(path):
            print(f"[!] INFO: {path} is empty. (Expected for new installs, verify if mount failed)")
    except Exception as e:
        print(f"[X] CRITICAL: Cannot access DATA_DIR at {path}: {e}")
        return False

    # Capacity Check: Warn if < 10GB
    try:
        total, used, free = shutil.disk_usage(path)
        free_gb = free // (2**30)
        if free_gb < 10:
            print(f"[!] WARNING: Low disk space on DATA_DIR ({free_gb}GB remaining)")
        else:
            print(f"[OK] DATA_DIR capacity healthy ({free_gb}GB free)")
    except Exception as e:
        print(f"[!] WARNING: Could not verify capacity for {path}: {e}")

    return True

def check_env() -> tuple[bool, list[str]]:
    """Verify required and optional environment variables."""
    missing_required = [e for e in REQUIRED_ENV if not os.getenv(e)]
    missing_optional = [e for e in OPTIONAL_ENV if not os.getenv(e)]
    
    if missing_required:
        for m in missing_required:
            print(f"[X] CRITICAL: Missing required environment variable: {m}")
        return False, missing_optional
    
    if missing_optional:
        for m in missing_optional:
            print(f"[!] WARNING: Missing optional environment variable: {m} (Tunnel will be DEGRADED)")
            
    return True, missing_optional

def run_preflight() -> str:
    """Executes all preflight checks and returns system status."""
    print("--- [PREFLIGHT] Starting Validation ---")
    
    mount_ok = check_mount()
    env_ok, missing_opt = check_env()
    
    if not mount_ok:
        print("[X] PREFLIGHT FAILED: Critical storage dependency missing.")
        return "CRITICAL"
    
    if not env_ok:
        print("[X] PREFLIGHT FAILED: Critical environment configuration missing.")
        return "CRITICAL"
    
    if missing_opt:
        print("[#] PREFLIGHT OK: System starting in DEGRADED mode.")
        return "DEGRADED"
    
    print("[V] PREFLIGHT SUCCESS: System healthy.")
    return "OK"

if __name__ == "__main__":
    status = run_preflight()
    if status == "CRITICAL":
        sys.exit(1)
    sys.exit(0)
