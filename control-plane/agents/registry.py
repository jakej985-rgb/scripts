import sys
import os
import re
import yaml

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import REGISTRY_JSON, DOCKER_DIR
from utils.state import save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("registry")

def get_containers_from_compose(file_path):
    containers = set()
    try:
        with open(file_path, 'r') as f:
            # Try proper YAML parsing
            data = yaml.safe_load(f)
            if data and 'services' in data:
                for service_name, config in data['services'].items():
                    # Prefer container_name if defined
                    c_name = config.get('container_name', service_name)
                    containers.add(c_name)
    except Exception as e:
        logger.warning(f"Failed to parse YAML {file_path}, falling back to regex: {e}")
        # Regex fallback for container_name:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                matches = re.findall(r'container_name:\s*([a-zA-Z0-9_\-\.]+)', content)
                for name in matches:
                    containers.add(name)
        except:
            pass
    return containers

def scan_for_containers():
    """Phase 1: Dynamic Registry scan as per Audit Batch 2 T3."""
    all_containers = set()
    
    # Scan docker/ directory recursively for docker-compose.yml files
    for root, dirs, files in os.walk(DOCKER_DIR):
        for file in files:
            if file.endswith('.yml') or file.endswith('.yaml'):
                full_path = os.path.join(root, file)
                # Skip example files or non-compose files
                if "example" in file.lower():
                    continue
                
                logger.debug(f"Scanning {full_path}")
                found = get_containers_from_compose(full_path)
                logger.info(f"Found {len(found)} containers in {full_path}")
                all_containers.update(found)
    
    # Filter out empty or invalid names
    valid_containers = sorted([c for c in all_containers if c])
    
    registry_data = {
        "containers": valid_containers,
        "paths": {
            "root": "/mnt",
            "downloads": "/mnt/downloads",
            "media": "/mnt/media"
        },
        "updated_at": os.path.getmtime(DOCKER_DIR) if os.path.exists(DOCKER_DIR) else 0
    }
    
    if save_json(REGISTRY_JSON, registry_data, caller="registry"):
        logger.info(f"Registry updated with {len(valid_containers)} containers. (Path: {os.path.abspath(REGISTRY_JSON)})")
    else:
        # Detailed error logging already handled by save_json, but we add context
        logger.error(f"Registry update failed for {os.path.abspath(REGISTRY_JSON)}")

if __name__ == "__main__":
    wrap_agent("registry", scan_for_containers)
