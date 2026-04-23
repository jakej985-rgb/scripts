#!/usr/bin/env python3
"""
M3TAL Global Blackout — Unified Shutdown Engine
v2.1.0 — Premium UI & Agent-Aware Teardown
"""

import subprocess
import os
import sys
import time
import json
from pathlib import Path
from pathlib import Path

# Fix for imports
BASE_DIR = Path(__file__).resolve().parent  # control-plane/
REPO_ROOT = BASE_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
AGENTS_DIR = BASE_DIR / "agents"
sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "helpers"))

from progress_utils import (
    Header, ProgressBar, SubProgressBar, LiveList, Heartbeat, GREEN,
    YELLOW, RED, BOLD, END
)
from utils.env import load_env

# --- Configuration ------------------------------------------------------------
DOCKER_DIR = REPO_ROOT / "docker"
STATE_DIR = BASE_DIR / "state"

# Stacks to shut down in order (most dependent first)
STACKS = [
    "control-plane",
    "media", 
    "network", 
    "maintenance", 
    "routing"
]

# --- Internal Helpers ---------------------------------------------------------
GLOBAL_ENV = load_env(REPO_ROOT)

HB = None

def terminate_agents():
    """Finds and terminates M3TAL autonomous agents."""
    HB.ping("Stopping autonomous agents")
    HB.log("Cleaning up autonomous agent runtime...")
    
    target_scripts = ["run.py", "healer.py", "supervisor.py", "init.py"]
    current_pid = os.getpid()
    
    if os.name == "nt":
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['pid'] == current_pid: continue
                cmdline = proc.info.get('cmdline')
                if cmdline and any(s in ' '.join(cmdline) for s in target_scripts):
                    HB.log(f"Terminating orphan process {proc.info['pid']} ({' '.join(cmdline[:3])})", symbol="⚠")
                    try:
                        proc.terminate()
                    except Exception:
                        subprocess.run(["taskkill", "/F", "/PID", str(proc.info['pid'])], capture_output=True)
        except ImportError:
            for script in target_scripts:
                subprocess.run(["taskkill", "/F", "/FI", f"cmdline eq *{script}*", "/FI", "IMAGENAME ne python.exe"], 
                             capture_output=True)
                # Fallback: kill based on script name if we can match it
                subprocess.run(["taskkill", "/F", "/FI", f"cmdline eq *{script}*"], 
                             capture_output=True)
    else:
        for script in target_scripts:
            # Audit Fix M9: Tighten pkill pattern to avoid matching unintended processes
            subprocess.run(["pkill", "-f", f"control-plane/agents/{script}"], capture_output=True)
            subprocess.run(["pkill", "-f", f"python.*{script}"], capture_output=True)
            
    HB.log("Clearing healer and agent locks")
    # Clean all lock files
    locks_dir = STATE_DIR / "locks"
    (locks_dir / "healer.lock").unlink(missing_ok=True)
    if locks_dir.exists():
        for f in locks_dir.glob("*"):
            try:
                if f.is_file(): f.unlink()
            except Exception: pass

def shutdown_stack(stack_name: str, bar: ProgressBar, current_step: int):
    """Surgically stops and removes a specific Docker stack."""
    if stack_name == "control-plane":
        stack_path = REPO_ROOT / "control-plane"
    else:
        stack_path = DOCKER_DIR / stack_name
    compose_file = stack_path / "docker-compose.yml"
    
    if not compose_file.exists():
        bar.update(current_step, f"Skipping {stack_name} (missing)")
        return

    HB.ping(f"Dismantling {stack_name}")
    HB.log(f"Dismantling {stack_name} stack...")
    
    # Pre-check: Is the stack actually up?
    ps_inspect = subprocess.run(["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
                                 capture_output=True, text=True, env=GLOBAL_ENV)

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
    conf_res = subprocess.run(conf_cmd, capture_output=True, text=True, env=GLOBAL_ENV)

    expected_services = conf_res.stdout.strip().splitlines() if conf_res.returncode == 0 else []
    total_svc = len(expected_services)
    
    with SubProgressBar(total_svc) as sub_bar, LiveList(expected_services) as live_list:
        sub_bar.update(0, f"Dismantling {total_svc} services ({stack_name})")

        try:
            # 1. Start deconstruction asynchronously
            # FIXED: Using stderr=DEVNULL to avoid "Pipe Deadlock" during teardown
            env_file = str(REPO_ROOT / ".env")
            proc = subprocess.Popen(["docker", "compose", "--env-file", env_file, "down", "--remove-orphans"], 
                                    cwd=str(stack_path), 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=GLOBAL_ENV)

            
            # Settle time
            time.sleep(1)
            
            # 2. Poll for removal immediately
            start_time = time.time()
            while time.time() - start_time < 120:
                ps_res = subprocess.run(["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
                                     capture_output=True, text=True, env=GLOBAL_ENV)

                if ps_res.returncode == 0:
                    out = ps_res.stdout.strip()
                    ps_data = []
                    try:
                        if out.startswith("["): ps_data = json.loads(out)
                        elif out: ps_data = [json.loads(l) for l in out.splitlines()]
                    except Exception: pass
                    
                    # (Audit Fix M1) Robust matching for Service or Name keys (Docker version variability)
                    remaining_items = [
                        item for item in expected_services 
                        if any((c.get("Service") == item or c.get("Name", "").endswith(f"-{item}-1")) for c in ps_data)
                    ]
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
            
            proc.wait()
                
        except Exception as e:
            HB.log(f"Dismantle Error in {stack_name}: {e}", symbol="\u2718")

    bar.update(current_step, f"Dismantled {stack_name}")

def main():
    global HB
    target_stacks = STACKS
    
    # Simple argument parsing for selective shutdown
    if len(sys.argv) > 1:
        provided = sys.argv[1:]
        # Filter global STACKS based on user input, preserving order
        target_stacks = [s for s in STACKS if any(p.lower() == s.split("/")[-1].lower() or p.lower() == s.lower() for p in provided)]
        
        if not target_stacks:
            print(f"{RED}Error: None of the provided stacks match known M3TAL stacks.{END}")
            print(f"Known stacks: {', '.join(STACKS)}")
            sys.exit(1)
            
        Header.show("M3TAL Selective Shutdown", f"Terminating: {', '.join(target_stacks)}")
    else:
        Header.show("M3TAL Global Blackout", "Autonomous Deconstruction Sequence")
    
    HB = Heartbeat()
    HB.start()
    # Progress: Agents (step 0) + Target Stacks + Network Prune (final step)
    bar = ProgressBar(len(target_stacks) + 1, prefix="Blackout")
    HB.tether(bar)

    try:
        # 1. Agents (Only if we are doing a broad shutdown or control-plane is involved)
        # For safety and predictability, we always run agent cleanup unless specifically told otherwise,
        # but for selective stack shutdown, we'll keep it as the first step.
        bar.update(0, "Agents")
        terminate_agents()
        time.sleep(1)

        # 2. Stacks
        for i, stack in enumerate(target_stacks, 1):
            shutdown_stack(stack, bar, i)
        
        # 3. Networks
        HB.ping("Pruning network space")
        HB.log("Pruning dangling Docker networks...")
        try:
            subprocess.run(["docker", "network", "prune", "-f"], check=False, 
                         env=GLOBAL_ENV, capture_output=True)

            HB.log("Global network space cleared", symbol="✔")
        except Exception: pass

        bar.update(len(target_stacks) + 1, "Complete")
        
    finally:
        HB.stop()

    print(f"\n{GREEN}{BOLD}[SUCCESS] Shutdown Sequence Complete.{END}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutdown interrupted by user.{END}")
        sys.exit(0)
