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
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse container JSON line: {line}")
                    continue
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
    
    # 1. Batch Discovery (Audit Fix 6.6 — M5 Performance Win)
    # Collect all names for a single batched inspect call
    container_names = [c.get("Names", "").lstrip("/") for c in docker_containers if c.get("Names")]
    inspect_data = {}
    
    if container_names:
        try:
            # We fetch both labels and config in one go
            inspect_cmd = ["docker", "inspect"] + container_names + ["--format", "{{json .Config.Labels}}"]
            inspect_res = subprocess.run(inspect_cmd, capture_output=True, text=True, check=True, timeout=15)
            # Docker inspect returns one JSON object per line with this format
            raw_labels = inspect_res.stdout.strip().splitlines()
            for i, name in enumerate(container_names):
                if i < len(raw_labels):
                    try:
                        inspect_data[name] = json.loads(raw_labels[i])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse inspect labels for {name}: {raw_labels[i]}")
                        inspect_data[name] = {}
        except Exception as e:
            logger.error(f"Batched inspect failed: {e}")

    # 2. Map and Register
    for container in docker_containers:
        name = container.get("Names", "").lstrip("/")
        if not name: continue
        
        labels = inspect_data.get(name, {})
        stack = labels.get("m3tal.stack", "unknown")
        service = labels.get("com.docker.compose.service", name)
        
        registry_containers.append(name)
        stack_map[name] = {
            "stack": stack,
            "service": service,
            "status": container.get("Status", "unknown"),
            "state": container.get("State", "unknown")
        }


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
