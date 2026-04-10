#!/usr/bin/env python3
"""
M3TAL Global Blackout — Unified, Cross-Platform Shutdown Engine
v2.0.0 — Agent-Aware & Self-Healing Compatible
"""

import subprocess
import os
import sys
import time
import signal
from pathlib import Path

# --- Platform-Aware Color Support ---------------------------------------------
if os.name == 'nt':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# ANSI colors
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"

# --- Context Anchoring --------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent
DOCKER_DIR = REPO_ROOT / "docker"
STATE_DIR = BASE_DIR / "state"

# Stacks to shut down in order (most dependent last)
STACKS = [
    "media", 
    "apps/tattoo-app", 
    "core", 
    "maintenance", 
    "routing"
]

def terminate_agents():
    """Finds and terminates M3TAL autonomous agents."""
    print(f"{YELLOW}Terminating autonomous agents...{END}")
    
    # Identify scripts to stop
    target_scripts = ["run.py", "healer.py"]
    
    if os.name == "nt":
        # Windows approach: find python processes with these names
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                cmdline = proc.info.get('cmdline')
                if cmdline and any(s in ' '.join(cmdline) for s in target_scripts):
                    print(f"  Stopping agent {proc.info['pid']}...")
                    proc.terminate()
        except ImportError:
            # Fallback if psutil is missing
            for script in target_scripts:
                subprocess.run(["taskkill", "/F", "/FI", f"cmdline eq *{script}*"], 
                             capture_output=True, shell=True)
    else:
        # Unix approach: pkill
        for script in target_scripts:
            subprocess.run(["pkill", "-f", script], capture_output=True)
            
    # Cleanup locks
    print(f"  Cleaning up locks...")
    (STATE_DIR / "healer.lock").unlink(missing_ok=True)
    locks_dir = STATE_DIR / "locks"
    if locks_dir.exists():
        for f in locks_dir.glob("*.pid"):
            f.unlink()

def shutdown_stack(stack_name: str):
    """Surgically stops and removes a specific Docker stack."""
    stack_path = DOCKER_DIR / stack_name
    compose_file = stack_path / "docker-compose.yml"
    
    if not compose_file.exists():
        return

    print(f"{YELLOW}Shutting down stack: {BOLD}{stack_name}{END}...")
    
    # We use 'docker compose down' for clean teardown of containers, networks, and orphans
    cmd = ["docker", "compose", "down", "--remove-orphans"]
    
    try:
        use_shell = os.name == "nt"
        subprocess.run(cmd, cwd=str(stack_path), shell=use_shell, check=True, capture_output=True)
        print(f"{GREEN} [OK] Stack {stack_name} dismantled.{END}")
    except subprocess.CalledProcessError as e:
        # Check if it was just because stack wasn't up
        if "no such service" not in (e.stderr or "").decode().lower():
            print(f"{RED} [FAIL] Failed to dismantle {stack_name}: {e}{END}")
    except Exception as e:
        print(f"{RED} [ERR] ERROR: {e}{END}")

def main():
    print(f"\n{BOLD}{RED}[!] M3TAL GLOBAL BLACKOUT INITIATED{END}")
    print(f"Repo Root: {BOLD}{REPO_ROOT}{END}")
    
    # 1. Stop Agents first to prevent "Healing" during shutdown
    terminate_agents()
    time.sleep(2) # Give them a moment to cleanup

    # 2. Tiered Stack Shutdown
    for stack in STACKS:
        shutdown_stack(stack)
    
    # 3. Final Network Cleaning
    print(f"\n{BOLD}Cleaning up dangling networks...{END}")
    try:
        subprocess.run(["docker", "network", "prune", "-f"], check=False, shell=(os.name == "nt"), capture_output=True)
        print(f"{GREEN} [OK] Global network space cleared.{END}")
    except Exception:
        pass

    print(f"\n{BOLD}{GREEN}[SUCCESS] M3TAL Shutdown Sequence Complete.{END}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutdown interrupted by user.{END}")
        sys.exit(0)
