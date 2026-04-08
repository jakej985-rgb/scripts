import subprocess
import json
import sys
import os

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR
from utils.state import save_json, load_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("monitor")
HEALTH_JSON = os.path.join(STATE_DIR, "health.json")
REGISTRY_JSON = os.path.join(STATE_DIR, "registry.json")

def collect_health():
    # Load registry to know what to monitor
    registry = load_json(REGISTRY_JSON, default={"containers": []})
    targets = registry.get("containers", [])
    
    cmd = ["docker", "ps", "-a", "--format", "{{json .}}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except Exception as e:
        logger.error(f"Failed to poll docker: {e}")
        return

    running_containers = {}
    for line in result.stdout.strip().split('\n'):
        if line:
            c = json.loads(line)
            name = c.get("Names", "")
            # Handle potential multi-name strings
            name = name.split(',')[0] 
            running_containers[name] = c

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
            
    save_json(HEALTH_JSON, health_status)
    logger.info(f"Health check completed for {len(targets)} containers.")

if __name__ == "__main__":
    wrap_agent("monitor", collect_health)
