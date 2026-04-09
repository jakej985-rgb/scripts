import sys
import os
import subprocess
import json
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import DECISIONS_JSON, REGISTRY_JSON, DOCKER_DIR, CONFIG_DIR, HEALTH_JSON, STATE_DIR
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("reconcile")

DEPENDENCIES_FILE = os.path.join(CONFIG_DIR, "dependencies.conf")

def load_dependencies():
    deps = []
    if not os.path.exists(DEPENDENCIES_FILE):
        return deps
    with open(DEPENDENCIES_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                app, dep = line.split(":", 1)
                deps.append((app.strip(), dep.strip()))
    return deps

def perform_action(action):
    a_type = action.get("type")
    target = action.get("target")
    reason = action.get("reason")
    
    logger.info(f"ACTION: {a_type} on {target} (Reason: {reason})")
    
    if a_type == "scale":
        return perform_scale(action)
        
    cmd = ["docker", a_type, target]
    if a_type not in ["restart", "start", "stop"]:
        logger.warning(f"Unsupported action type: {a_type}")
        return False
        
    try:
        # Batch 5 T2: Removed shell=True for security
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to execute {a_type} on {target}: {e.stderr}")
        return False

def perform_scale(action):
    target = action.get("target")
    direction = action.get("direction")
    for root, dirs, files in os.walk(DOCKER_DIR):
        for file in files:
            if file.endswith('.yml') or file.endswith('.yaml'):
                full_path = os.path.join(root, file)
                try:
                    res = subprocess.run(["docker", "compose", "-f", full_path, "ps", target], capture_output=True, text=True)
                    if res.returncode == 0 and target in res.stdout:
                        num = 2 if direction == "up" else 1
                        logger.info(f"Scaling {target} {direction} to {num} replicas")
                        subprocess.run(["docker", "compose", "-f", full_path, "up", "-d", "--scale", f"{target}={num}"], check=True)
                        return True
                except:
                    continue
    return False

def enforce_dependencies():
    """Batch 5 T1: Ensure dependencies are running."""
    deps = load_dependencies()
    health = load_json(HEALTH_JSON, default={})
    
    for app, dep in deps:
        # Check if app is supposed to be running but dep is not
        if app in health and health[app].get("status") == "online":
            # If dep is a container (not a path)
            if not dep.startswith("/"):
                if dep in health and health[dep].get("status") == "offline":
                    logger.warning(f"Dependency Violation: {app} is running but {dep} is stopped. Starting {dep}...")
                    subprocess.run(["docker", "start", dep])

def check_storage_enforcement():
    registry = load_json(REGISTRY_JSON, default={"containers": []})
    containers = registry.get("containers", [])
    for c in containers:
        try:
            cmd = ["docker", "inspect", c, "--format", "{{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                mounts = res.stdout.strip()
                if "/mnt:/mnt" not in mounts:
                    logger.warning(f"Storage Violation: {c} missing /mnt:/mnt mount!")
        except Exception as e:
            logger.debug(f"Could not inspect {c}: {e}")

def reconcile():
    # 1. Dependency Enforcement First
    enforce_dependencies()
    
    # 2. Process Decisions (from decision.py)
    decisions = load_json(DECISIONS_JSON, default={"actions": []})
    actions = decisions.get("actions", [])
    
    # 2b. Merge scaling actions (from scaling.py — Audit fix 2.3)
    scaling_file = os.path.join(STATE_DIR, "scaling_actions.json")
    scaling_data = load_json(scaling_file, default={"actions": []})
    actions.extend(scaling_data.get("actions", []))
    
    if actions:
        logger.info(f"Processing {len(actions)} actions...")
        for action in actions:
            perform_action(action)
        save_json(DECISIONS_JSON, {"actions": []})
        save_json(scaling_file, {"actions": []})
        
    # 3. Storage Enforcement (Time-gated to 5 mins - Audit fix 2.9)
    last_storage_file = os.path.join(STATE_DIR, "last_storage.json")
    last_st = load_json(last_storage_file, default={"ts": 0})
    if time.time() - last_st.get("ts", 0) > 300:
        check_storage_enforcement()
        save_json(last_storage_file, {"ts": time.time()})
    
    logger.info("Reconciliation cycle complete.")

if __name__ == "__main__":
    wrap_agent("reconcile", reconcile)
