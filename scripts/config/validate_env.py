#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Add scripts subfolders to path for sibling imports
for sub in ["config", "helpers"]:
    sys.path.append(str(REPO_ROOT / "scripts" / sub))

try:
    from configure_env import REQUIRED_VARS, ENV_FILE, YELLOW, RED, GREEN, BOLD, END
except ImportError:
    # Fallback if import fails
    REQUIRED_VARS = ["REPO_ROOT", "MASTER_IP", "DASHBOARD_PORT", "HTTP_PORT", "DATA_DIR", "CONFIG_DIR", "DOMAIN", "VPN_USER", "VPN_PASSWORD", "DASHBOARD_SECRET", "TELEGRAM_BOT_TOKEN"]
    ENV_FILE = os.path.join(REPO_ROOT, ".env")
    YELLOW, RED, GREEN, BOLD, END = ("", "", "", "", "")

def load_env():
    """Autonomous Environment Loader: Inject .env into os.environ if not already present."""
    if not os.path.exists(ENV_FILE):
        return
    
    with open(ENV_FILE, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'") # Handle quoted values
            
            if key and key not in os.environ:
                os.environ[key] = val

def validate_env(interactive=False):
    """Rex Guardrail: Verify .env integrity before execution."""
    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    
    if not os.path.exists(ENV_FILE):
        if is_ci:
            print(f"{YELLOW}[REX] CI Environment: .env file is missing. Skipping fatal audit.{END}")
            return True, []
            
        print(f"{RED}{BOLD}[REX] ERROR: .env file is missing!{END}")
        if interactive:
            print(f"{YELLOW}Hint: Run 'python scripts/config/configure_env.py' to generate it.{END}")
        return False, []

    missing = []
    # Rex Fix: Force UTF-8 for cross-platform emoji support (.env contains icons)
    with open(ENV_FILE, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
        for var in REQUIRED_VARS:
            if f"{var}=" not in content:
                missing.append(var)

    if missing:
        print(f"{RED}{BOLD}[REX] ERROR: Missing required environment variables in .env:{END}")
        for m in missing:
            print(f"  - {m}")
        if interactive:
            print(f"\n{YELLOW}Hint: Run 'python scripts/config/configure_env.py' to update your configuration.{END}")
        return False, missing

    print(f"{GREEN}[REX] Environment integrity verified.{END}")
    return True, []

if __name__ == "__main__":
    valid, _ = validate_env(interactive=True)
    if not valid:
        sys.exit(1)
    sys.exit(0)
