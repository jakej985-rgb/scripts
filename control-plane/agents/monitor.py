import subprocess
import json
import sys
import os

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, REGISTRY_JSON
from utils.state import save_json, load_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("monitor")

# Batch 5 T3: Per-agent status file
STATUS_FILE = os.path.join(STATE_DIR, "health", "monitor_containers.json")

def collect_health():
    registry = load_json(str(REGISTRY_JSON), default={"containers": []})
    targets = registry.get("containers", [])
    
    cmd = ["docker", "ps", "-a", "--format", "{{json .}}"]
    try:
        # Rex Fix: capture_output and text enabled to see meaningful errors
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to poll docker (Status {e.returncode})")
        if e.stderr:
            logger.error(f"DOCKER_STDERR: {e.stderr.strip()}")
        return
    except Exception as e:
        logger.error(f"Failed to poll docker: {e}")
        return

    running_containers = {}
    for line in result.stdout.strip().split('\n'):
        if line:
            try:
                c = json.loads(line)
                name = c.get("Names", "").split(',')[0] 
                running_containers[name] = c
            except json.JSONDecodeError:
                continue

    health_status = {}
    for target in targets:
        if target in running_containers:
            status = running_containers[target].get("Status", "unknown")
            is_up = "Up" in status
            health_status[target] = {
                "status": "online" if is_up else "offline",
                "raw_status": status,
                "created": running_containers[target].get("CreatedAt")
            }
        else:
            health_status[target] = {
                "status": "missing",
                "raw_status": "not found"
            }
            
    # Save to the per-agent file (Batch 5 T3)
    save_json(STATUS_FILE, health_status, caller="monitor")
    logger.info(f"Health check completed for {len(targets)} containers.")

if __name__ == "__main__":
    wrap_agent("monitor", collect_health)
