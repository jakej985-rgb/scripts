import sys
import os
import subprocess
import json
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import DECISIONS_JSON, REGISTRY_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("reconcile")

def perform_action(action):
    a_type = action.get("type")
    target = action.get("target")
    reason = action.get("reason")
    
    logger.info(f"ACTION: {a_type} on {target} (Reason: {reason})")
    
    cmd = ["docker", a_type, target]
    if a_type not in ["restart", "start", "stop"]:
        logger.warning(f"Unsupported action type: {a_type}")
        return False
        
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to execute {a_type} on {target}: {e.stderr}")
        return False

def check_storage_enforcement():
    """Ensure all managed containers use /mnt as per AGENT_PLAN.md."""
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
    """Phase 3: Reconcile Agent in Python as per Audit Batch 2 T5."""
    decisions = load_json(DECISIONS_JSON, default={"actions": []})
    actions = decisions.get("actions", [])
    
    if not actions:
        logger.info("No pending actions.")
    else:
        logger.info(f"Processing {len(actions)} actions...")
        for action in actions:
            perform_action(action)
            
        # Task 6: Clear decisions after execution for idempotency
        save_json(DECISIONS_JSON, {"actions": []})
        
    # Task 6: Storage Enforcement
    check_storage_enforcement()
    
    logger.info("Reconciliation cycle complete.")

if __name__ == "__main__":
    wrap_agent("reconcile", reconcile)
