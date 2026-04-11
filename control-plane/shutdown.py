#!/usr/bin/env python3
"""
M3TAL Global Blackout — Unified Shutdown Engine
v2.1.0 — Premium UI & Agent-Aware Teardown
"""

import subprocess
import os
import sys
import time
from pathlib import Path

# Fix for imports
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from progress_utils import (
    Header, ProgressBar, SubProgressBar, LiveList, Heartbeat, Spinner,
    CYAN, GREEN, YELLOW, RED, BOLD, END, DIM
)

# --- Configuration ------------------------------------------------------------
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

HB = Heartbeat()

def terminate_agents():
    """Finds and terminates M3TAL autonomous agents."""
    HB.ping("Stopping autonomous agents")
    HB.log("Cleaning up autonomous agent runtime...")
    
    target_scripts = ["run.py", "healer.py"]
    
    if os.name == "nt":
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                cmdline = proc.info.get('cmdline')
                if cmdline and any(s in ' '.join(cmdline) for s in target_scripts):
                    HB.log(f"Terminating agent process {proc.info['pid']}", symbol="⚠")
                    proc.terminate()
        except ImportError:
            for script in target_scripts:
                subprocess.run(["taskkill", "/F", "/FI", f"cmdline eq *{script}*"], 
                             capture_output=True, shell=True)
    else:
        for script in target_scripts:
            subprocess.run(["pkill", "-f", script], capture_output=True)
            
    HB.log("Clearing healer and agent locks")
    (STATE_DIR / "healer.lock").unlink(missing_ok=True)
    locks_dir = STATE_DIR / "locks"
    if locks_dir.exists():
        for f in locks_dir.glob("*.pid"):
            f.unlink()

def shutdown_stack(stack_name: str, bar: ProgressBar, current_step: int):
    """Surgically stops and removes a specific Docker stack."""
    stack_path = DOCKER_DIR / stack_name
    compose_file = stack_path / "docker-compose.yml"
    use_shell = os.name == "nt"
    
    if not compose_file.exists():
        bar.update(current_step, f"Skipping {stack_name} (missing)")
        return

    HB.ping(f"Dismantling {stack_name}")
    HB.log(f"Dismantling {stack_name} stack...")
    
    # Pre-check: Is the stack actually up?
    ps_inspect = subprocess.run(["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
                                 capture_output=True, text=True, shell=use_shell)
    is_up = False
    if ps_inspect.returncode == 0 and ps_inspect.stdout.strip():
        # If ps returns any json objects, the stack has containers (even if exited)
        is_up = True
    
    if not is_up:
        HB.log(f"Stack {stack_name} is already down. Skipping.", symbol="✔")
        bar.update(current_step, f"Skipped {stack_name} (Already Down)")
        return

    # Identify containers before removal
    conf_cmd = ["docker", "compose", "-f", str(compose_file), "config", "--services"]
    conf_res = subprocess.run(conf_cmd, capture_output=True, text=True, shell=use_shell)
    expected_services = conf_res.stdout.strip().splitlines() if conf_res.returncode == 0 else []
    total_svc = len(expected_services)
    
    sub_bar = SubProgressBar(total_svc)
    live_list = LiveList(expected_services)
    sub_bar.update(0, f"Dismantling {total_svc} services ({stack_name})")

    try:
        # 1. Start deconstruction asynchronously
        proc = subprocess.Popen(["docker", "compose", "down", "--remove-orphans"], 
                                cwd=str(stack_path), shell=use_shell, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. Poll for removal immediately
        start_time = time.time()
        while time.time() - start_time < 120:
            ps_res = subprocess.run(["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
                                 capture_output=True, text=True, shell=use_shell)
            if ps_res.returncode == 0:
                out = ps_res.stdout.strip()
                ps_data = []
                try:
                    if out.startswith("["): ps_data = json.loads(out)
                    elif out: ps_data = [json.loads(l) for l in out.splitlines()]
                except: pass
                
                remaining_items = [item for item in expected_services if any(c.get("Service") == item for c in ps_data)]
                remaining_count = len(remaining_items)
                removed_count = total_svc - remaining_count
                
                # Update individual statuses
                for item in expected_services:
                    if item in remaining_items:
                        live_list.update(item, "terminating...")
                    else:
                        live_list.update(item, "removed")

                sub_bar.update(removed_count, f"Removed {removed_count}/{total_svc} ({stack_name})")
                if remaining_count == 0: break
            time.sleep(1.5)
        
        live_list.reset()
            
    except Exception as e:
        HB.log(f"Dismantle Error in {stack_name}: {e}", symbol="✘")
        if 'live_list' in locals(): live_list.reset()

    bar.update(current_step, f"Dismantled {stack_name}")

def main():
    Header.show("M3TAL Global Blackout", "Autonomous Deconstruction Sequence")
    
    HB.start()
    bar = ProgressBar(len(STACKS) + 1, prefix="Blackout")
    HB.tether(bar)

    try:
        # 1. Agents
        bar.update(0, "Agents")
        terminate_agents()
        time.sleep(1)

        # 2. Stacks
        for i, stack in enumerate(STACKS, 1):
            shutdown_stack(stack, bar, i)
        
        # 3. Networks
        HB.ping("Pruning network space")
        HB.log("Pruning dangling Docker networks...")
        try:
            subprocess.run(["docker", "network", "prune", "-f"], check=False, shell=(os.name == "nt"), capture_output=True)
            HB.log("Global network space cleared", symbol="✔")
        except: pass

        bar.update(len(STACKS) + 1, "Complete")
        
    finally:
        HB.stop()

    print(f"\n{GREEN}{BOLD}[SUCCESS] M3TAL Shutdown Sequence Complete.{END}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutdown interrupted by user.{END}")
        sys.exit(0)
