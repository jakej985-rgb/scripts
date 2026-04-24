import sys
import os
import subprocess
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import DECISIONS_JSON, REGISTRY_JSON, CONFIG_DIR, STATE_DIR, REPO_ROOT, CONTAINER_HEALTH_JSON
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
        
    if a_type == "redeploy":
        return perform_redeploy(action)

    # Allowlist-first: only permit known safe Docker commands
    ALLOWED_ACTIONS = {"restart", "start", "stop"}
    if a_type not in ALLOWED_ACTIONS:
        logger.warning(f"Unsupported action type: {a_type}")
        return False
        
    cmd = ["docker", a_type, target]
    try:
        # Tweak 4: Subprocess timeout and explicit error handling
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"Action {a_type} on {target} timed out (15s)")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to execute {a_type} on {target}: {e.stderr}")
        return False

def perform_scale(action):
    target = action.get("target")
    direction = action.get("direction")
    
    registry = load_json(REGISTRY_JSON, default={})
    compose_index = registry.get("compose_index", {})
    
    full_path = compose_index.get(target)
    if not full_path:
        logger.error(f"Cannot scale {target}: compose file not found in registry index.")
        return False
        
    env_file = os.path.join(REPO_ROOT, ".env")
    env_arg = ["--env-file", env_file] if os.path.exists(env_file) else []
    try:
        res = subprocess.run(["docker", "compose", "-f", full_path, "ps", target], capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and target in res.stdout:
            num = 2 if direction == "up" else 1
            logger.info(f"Scaling {target} {direction} to {num} replicas")
            cmd = ["docker", "compose", "-f", full_path] + env_arg + ["up", "-d", "--scale", f"{target}={num}"]
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            return True
    except subprocess.TimeoutExpired:
        logger.error(f"Scale check timed out for {target} in {full_path}")
    except Exception as e:
        logger.error(f"Error scaling {target}: {e}")
        
    return False

def perform_redeploy(action):
    target = action.get("target")
    logger.info(f"Attempting to redeploy missing service: {target}")
    
    registry = load_json(REGISTRY_JSON, default={})
    compose_index = registry.get("compose_index", {})
    
    full_path = compose_index.get(target)
    if not full_path:
        logger.error(f"Could not find compose context for service: {target}")
        return False
        
    # Batch 16 Hardening: Ensure we use --env-file if .env exists
    env_file = os.path.join(REPO_ROOT, ".env")
    env_arg = ["--env-file", env_file] if os.path.exists(env_file) else []
    
    logger.info(f"Found {target} in {full_path}. Redeploying...")
    cmd = ["docker", "compose", "-f", full_path] + env_arg + ["up", "-d", target]
    try:
        # Audit Fix H5: Increase timeout to 300s for large images
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"Redeploy check timed out for {target} in {full_path}")
    except Exception as e:
        logger.error(f"Error checking compose file {full_path}: {e}")
    
    return False

def enforce_dependencies():
    """Batch 5 T1: Ensure dependencies are running."""
    deps = load_dependencies()
    # Audit Fix 1.4: Use container-specific health rather than system report
    health_data = load_json(CONTAINER_HEALTH_JSON, default={})
    containers = health_data.get("containers", {})
    
    for app, dep in deps:
        # Check if app is supposed to be running but dep is not
        app_status = containers.get(app, {}).get("status")
        if app_status == "online":
            # If dep is a container (not a path)
            if not dep.startswith("/"):
                dep_status = containers.get(dep, {}).get("status")
                if dep_status == "offline" or dep_status == "missing":
                    logger.warning(f"Dependency Violation: {app} is running but {dep} is {dep_status}. Starting {dep}...")
                    try:
                        res = subprocess.run(["docker", "start", dep], timeout=15, capture_output=True, text=True)
                        if res.returncode != 0:
                            logger.error(f"Failed to start dependency {dep}: {res.stderr}")
                    except subprocess.TimeoutExpired:
                        logger.error(f"Dependency start timed out for {dep}")

def check_storage_enforcement():
    registry = load_json(REGISTRY_JSON, default={"stacks": {}})
    stacks = registry.get("stacks", {})
    
    for c, meta in stacks.items():
        # Audit Fix M1: Check for explicit storage requirement label
        if meta.get("labels", {}).get("m3tal.requires_storage") != "true":
            continue
            
        try:
            cmd = ["docker", "inspect", c, "--format", "{{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                mounts = res.stdout.strip()
                if ":/mnt" not in mounts:
                    logger.warning(f"Storage Violation: {c} missing :/mnt mount!")
                    # Try to start it just in case it was offline (Audit Fix H2 leak prevention)
                    res = subprocess.run(["docker", "start", c], capture_output=True, text=True, timeout=10)
                    if res.returncode != 0:
                        logger.debug(f"Attempt to start {c} after storage violation failed: {res.stderr}")
        except subprocess.TimeoutExpired:
            logger.error(f"Storage inspect timed out for {c}")
        except Exception as e:
            logger.debug(f"Could not inspect {c}: {e}")

def reconcile():
    # 1. Dependency Enforcement First
    enforce_dependencies()
    
    # 2. Process Decisions (from decision.py)
    decisions_data = load_json(DECISIONS_JSON, default={"actions": []})
    decision_actions = decisions_data.get("actions", [])
    
    # 2b. Process scaling actions (from scaling.py)
    scaling_file = os.path.join(STATE_DIR, "scaling_actions.json")
    scaling_data = load_json(scaling_file, default={"actions": []})
    scaling_actions = scaling_data.get("actions", [])
    
    # Durability logic (Audit Fix 6.6 — M7 Durability)
    # Only remove actions that successfully completed
    remaining_decisions = []
    remaining_scaling = []

    if decision_actions or scaling_actions:
        logger.info(f"Reconciling: {len(decision_actions)} decisions, {len(scaling_actions)} scaling requests")
        
        for action in decision_actions:
            # Audit Fix A1: Retry limit (Max 5) to prevent infinite loops on permanent failures
            retries = action.get("retry_count", 0)
            if perform_action(action):
                pass
            elif retries < 5:
                action["retry_count"] = retries + 1
                remaining_decisions.append(action)
            else:
                logger.error(f"Permanent Failure: Action {action.get('type')} on {action.get('target')} exceeded retry limit.")
        
        for action in scaling_actions:
            retries = action.get("retry_count", 0)
            if perform_action(action):
                pass
            elif retries < 5:
                action["retry_count"] = retries + 1
                remaining_scaling.append(action)
            else:
                logger.error(f"Permanent Failure: Scaling {action.get('target')} exceeded retry limit.")

        # Update queues with ONLY the failed/remaining items
        save_json(DECISIONS_JSON, {"actions": remaining_decisions}, caller="reconcile")
        save_json(scaling_file, {"actions": remaining_scaling}, caller="reconcile")
        
        if remaining_decisions or remaining_scaling:
            logger.warning(f"Durability: {len(remaining_decisions) + len(remaining_scaling)} actions failed and were retained in queue.")

        
    # 3. Storage Enforcement (Time-gated to 5 mins - Audit fix 2.9)
    last_storage_file = os.path.join(STATE_DIR, "last_storage.json")
    last_st = load_json(last_storage_file, default={"ts": 0})
    if time.time() - last_st.get("ts", 0) > 300:
        check_storage_enforcement()
        save_json(last_storage_file, {"ts": time.time()}, caller="reconcile")
    
    logger.info("Reconciliation cycle complete.")

if __name__ == "__main__":
    wrap_agent("reconcile", reconcile)
