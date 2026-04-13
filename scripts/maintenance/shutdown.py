#!/usr/bin/env python3
import subprocess
import os
import sys
import time
from pathlib import Path

# --- Context Anchoring --------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCKER_DIR = REPO_ROOT / "docker"

ENV_FILE = REPO_ROOT / ".env"

def shutdown_stack(stack_name: str):
    stack_path = DOCKER_DIR / stack_name
    compose_file = stack_path / "docker-compose.yml"
    
    if not compose_file.exists():
        return # Skip if no compose file

    print(f"{YELLOW}Shutting down stack: {BOLD}{stack_name}{END}...")
    
    # Audit Fix: Explicitly pass env-file and compose-file to respect root-authority model
    cmd = ["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(compose_file), "down", "--remove-orphans"]
    try:
        # Avoid cwd shift to maintain consistency with centralized execution
        use_shell = os.name == "nt"
        subprocess.run(cmd, shell=use_shell, check=True)
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
