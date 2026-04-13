import sys
import os
import json
import subprocess
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import REGISTRY_JSON
from utils.state import save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("registry")

def get_docker_containers():
    """Fetch containers using Docker API (cli) and filter by m3tal.stack label."""
    try:
        # We query for all containers with the label m3tal.stack
        cmd = [
            "docker", "ps", "-a", 
            "--filter", "label=m3tal.stack",
            "--format", "{{json .}}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        containers = []
        for line in result.stdout.splitlines():
            if line.strip():
                containers.append(json.loads(line))
        return containers
    except Exception as e:
        logger.error(f"Failed to query Docker API: {e}")
        return []

def scan_infrastructure():
    """
    Discovery Agent (Refactored for V2):
    - Uses Docker labels (m3tal.stack) instead of YAML parsing.
    - Maps container -> service -> stack.
    - Detects unhealthy states.
    """
    docker_containers = get_docker_containers()
    
    registry_containers = []
    stack_map = {}
    
    for container in docker_containers:
        name = container.get("Names")
        if not name: continue
        # Clean name (remove leading / if present)
        name = name.lstrip("/")
        
        # Get labels via docker inspect for more detail
        try:
            inspect_cmd = ["docker", "inspect", name, "--format", "{{json .Config.Labels}}"]
            inspect_res = subprocess.run(inspect_cmd, capture_output=True, text=True, check=True)
            labels = json.loads(inspect_res.stdout)
            
            stack = labels.get("m3tal.stack", "unknown")
            service = labels.get("com.docker.compose.service", name)
            
            registry_containers.append(name)
            stack_map[name] = {
                "stack": stack,
                "service": service,
                "status": container.get("Status", "unknown"),
                "state": container.get("State", "unknown")
            }
        except:
            logger.warning(f"Failed to inspect container {name}")

    registry_data = {
        "containers": sorted(registry_containers),
        "stacks": stack_map,
        "paths": {
            "root": "/mnt",
            "downloads": "/mnt/downloads",
            "media": "/mnt/media"
        },
        "updated_at": int(time.time())
    }
    
    try:
        if save_json(REGISTRY_JSON, registry_data, caller="registry"):
            logger.info(f"Registry updated with {len(registry_containers)} m3tal containers.")
        else:
            logger.error(f"Registry update failed for {os.path.abspath(REGISTRY_JSON)}")
    except Exception as e:
        logger.error(f"Unexpected error during registry update: {e}")

if __name__ == "__main__":
    wrap_agent("registry", scan_infrastructure)
