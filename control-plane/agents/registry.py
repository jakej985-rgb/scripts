import sys
import os
import json

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR
from utils.state import save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("registry")
REGISTRY_JSON = os.path.join(STATE_DIR, "registry.json")

# Define the "Single Source of Truth" as per Task 7
REGISTRY_DATA = {
    "containers": [
        "qbittorrent",
        "radarr",
        "sonarr",
        "tdarr"
    ],
    "paths": {
        "root": "/mnt",
        "downloads": "/mnt/downloads",
        "media": "/mnt/media"
    }
}

def update_registry():
    """Maintain the single source of truth for the system architecture."""
    # In a real system, this might poll docker-compose files or a CMDB,
    # but for now, we enforce the AGENT_PLAN.md definition.
    if save_json(REGISTRY_JSON, REGISTRY_DATA):
        logger.info("Registry updated successfully.")
    else:
        logger.error("Failed to update registry.")

if __name__ == "__main__":
    wrap_agent("registry", update_registry)
