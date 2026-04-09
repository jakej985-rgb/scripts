#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "scripts"))

try:
    from configure_env import REQUIRED_VARS, ENV_FILE, YELLOW, RED, GREEN, BOLD, END
except ImportError:
    # Fallback if import fails
    REQUIRED_VARS = ["MASTER_IP", "DASHBOARD_PORT", "HTTP_PORT", "DATA_DIR", "CONFIG_DIR", "DOMAIN", "VPN_USER", "VPN_PASSWORD", "DASHBOARD_SECRET"]
    ENV_FILE = os.path.join(REPO_ROOT, ".env")
    YELLOW, RED, GREEN, BOLD, END = ("", "", "", "", "")

def validate_env(interactive=False):
    """Rex Guardrail: Verify .env integrity before execution."""
    if not os.path.exists(ENV_FILE):
        print(f"{RED}{BOLD}[REX] ERROR: .env file is missing!{END}")
        if interactive:
            print(f"{YELLOW}Hint: Run 'python scripts/configure_env.py' to generate it.{END}")
        return False, []

    missing = []
    with open(ENV_FILE, 'r') as f:
        content = f.read()
        for var in REQUIRED_VARS:
            if f"{var}=" not in content:
                missing.append(var)

    if missing:
        print(f"{RED}{BOLD}[REX] ERROR: Missing required environment variables in .env:{END}")
        for m in missing:
            print(f"  - {m}")
        if interactive:
            print(f"\n{YELLOW}Hint: Run 'python scripts/configure_env.py' to update your configuration.{END}")
        return False, missing

    print(f"{GREEN}[REX] Environment integrity verified.{END}")
    return True, []

if __name__ == "__main__":
    valid, _ = validate_env(interactive=True)
    if not valid:
        sys.exit(1)
    sys.exit(0)
