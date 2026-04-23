import sys
import os
import json
import subprocess
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import REGISTRY_JSON
from utils.state import save_json, load_json
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
        for name in container_names:
            try:
                inspect_cmd = ["docker", "inspect", name, "--format", "{{json .Config.Labels}}|{{.State.StartedAt}}"]
                inspect_res = subprocess.run(inspect_cmd, capture_output=True, text=True, check=True, timeout=10)
                raw = inspect_res.stdout.strip()
                if "|" in raw:
                    labels_raw, started_at = raw.split("|", 1)
                    inspect_data[name] = {"labels": json.loads(labels_raw), "started_at": started_at}
                else:
                    inspect_data[name] = {"labels": json.loads(raw) if raw else {}, "started_at": "unknown"}
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse inspect labels for {name}")
                inspect_data[name] = {}
            except Exception as e:
                logger.warning(f"Inspect failed for {name}: {e}")
                inspect_data[name] = {}

    # 2. Map and Register
    for container in docker_containers:
        name = container.get("Names", "").lstrip("/")
        if not name: continue
        
        labels_info = inspect_data.get(name, {})
        labels = labels_info.get("labels", {})
        stack = labels.get("m3tal.stack", "unknown")
        service = labels.get("com.docker.compose.service", name)
        role = labels.get("m3tal.role", "unknown")
        started_at = labels_info.get("started_at", "unknown")
        
        registry_containers.append(name)
        stack_map[name] = {
            "stack": stack,
            "service": service,
            "role": role,
            "status": container.get("Status", "unknown"),
            "state": container.get("State", "unknown"),
            "started_at": started_at
        }

    # Audit Fix M2: Cache compose index and only rebuild periodically (every 5 mins)
    last_registry = load_json(REGISTRY_JSON, default={})
    cached_index = last_registry.get("compose_index", {})
    last_walk = last_registry.get("last_walk_ts", 0)
    
    if time.time() - last_walk < 300 and cached_index:
        compose_index = cached_index
    else:
        from utils.paths import DOCKER_DIR
        compose_index = {}
        for root, dirs, files in os.walk(DOCKER_DIR):
            for file in files:
                if file.endswith('.yml') or file.endswith('.yaml'):
                    full_path = os.path.join(root, file)
                    try:
                        res = subprocess.run(["docker", "compose", "-f", full_path, "config", "--services"], 
                                             capture_output=True, text=True, timeout=5)
                        if res.returncode == 0:
                            for svc in res.stdout.splitlines():
                                compose_index[svc.strip()] = full_path
                    except Exception as e:
                        logger.debug(f"Skipping {file} in registry index: {e}")
                        continue
        last_walk = int(time.time())

    registry_data = {
        "containers": sorted(registry_containers),
        "stacks": stack_map,
        "compose_index": compose_index,
        "last_walk_ts": last_walk,
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
