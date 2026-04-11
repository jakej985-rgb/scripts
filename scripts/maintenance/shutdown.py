#!/usr/bin/env python3
import subprocess
import os
import sys
import time
from pathlib import Path

# --- Context Anchoring --------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCKER_DIR = REPO_ROOT / "docker"

# Stacks to shut down in order (most dependent last)
STACKS = ["core", "media", "apps", "maintenance", "routing"]

# ANSI colors for nice UI
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"

def shutdown_stack(stack_name: str):
    stack_path = DOCKER_DIR / stack_name
    compose_file = stack_path / "docker-compose.yml"
    
    if not compose_file.exists():
        return # Skip if no compose file

    print(f"{YELLOW}Shutting down stack: {BOLD}{stack_name}{END}...")
    
    cmd = ["docker", "compose", "down", "--remove-orphans"]
    try:
        # Use shell=True on Windows for better compatibility with docker-compose shims
        use_shell = os.name == "nt"
        subprocess.run(cmd, cwd=str(stack_path), shell=use_shell, check=True)
        print(f"{GREEN}✓ Stack {stack_name} stopped.{END}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}✗ Failed to shut down {stack_name}: {e}{END}")

def main():
    print(f"\n{BOLD}{RED}🚨 M3TAL Global Shutdown Sequence Engine{END}")
    print(f"This will stop and remove all containers across the entire stack.\n")

    # Tiered shutdown to ensure no network/volume hangs
    for stack in STACKS:
        shutdown_stack(stack)
    
    # 2. Final Network Cleaning
    print(f"\n{BOLD}Cleaning up orphan networks...{END}")
    try:
        subprocess.run(["docker", "network", "prune", "-f"], check=True)
        print(f"{GREEN}✓ All networks cleared.{END}")
    except Exception:
        pass

    print(f"\n{BOLD}{GREEN}✅ M3TAL Shutdown Complete.{END}\n")

if __name__ == "__main__":
    main()
