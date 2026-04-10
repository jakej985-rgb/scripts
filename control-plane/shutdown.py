#!/usr/bin/env python3
"""
M3TAL Blackout — Unified, Cross-Platform Shutdown Engine
v1.0.0 — Pure Python Implementation
"""

import subprocess
import os
import sys
from pathlib import Path

# --- Platform-Aware Color Support ---------------------------------------------
if os.name == 'nt':
    # Enable ANSI support on Windows 10+
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
REPO_ROOT = Path(__file__).resolve().parent
DOCKER_DIR = REPO_ROOT / "docker"

# Stacks to shut down in order (most dependent last)
STACKS = ["media", "apps", "core", "maintenance", "routing"]

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
        # Use shell=True only on Windows for better compatibility with docker-compose shims
        use_shell = os.name == "nt"
        subprocess.run(cmd, cwd=str(stack_path), shell=use_shell, check=True)
        print(f"{GREEN}✓ Stack {stack_name} dismantled.{END}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}✗ Failed to dismantle {stack_name}: {e}{END}")
    except FileNotFoundError:
        print(f"{RED}✗ ERROR: 'docker' command not found. Is Docker installed?{END}")
        sys.exit(1)

def main():
    print(f"\n{BOLD}{RED}🚨 M3TAL GLOBAL BLACKOUT INITIATED{END}")
    print(f"Detecting stacks in: {BOLD}{DOCKER_DIR}{END}\n")

    # 1. Tiered Stack Shutdown
    for stack in STACKS:
        shutdown_stack(stack)
    
    # 2. Final Network Cleaning
    print(f"\n{BOLD}Cleaning up dangling networks...{END}")
    try:
        # Prune only networks to avoid accidental volume/image loss
        subprocess.run(["docker", "network", "prune", "-f"], check=False, shell=(os.name == "nt"))
        print(f"{GREEN}✓ Global network space cleared.{END}")
    except Exception:
        pass

    print(f"\n{BOLD}{GREEN}✅ M3TAL Shutdown Sequence Complete.{END}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutdown interrupted by user.{END}")
        sys.exit(0)
