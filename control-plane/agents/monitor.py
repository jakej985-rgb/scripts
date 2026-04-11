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
from utils.identity import match_container_safe

logger = get_logger("monitor")

# Batch 5 T3: Per-agent status file
STATUS_FILE = os.path.join(STATE_DIR, "health", "monitor_containers.json")

def collect_health():
    registry = load_json(str(REGISTRY_JSON), default={"containers": []})
    targets = registry.get("containers", [])
    
    cmd = ["docker", "ps", "-a", "--format", "{{json .}}"]
    now = int(time.time())
    
    try:
        # Tweak 4: Subprocess timeout handling
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
    except subprocess.TimeoutExpired:
        logger.error("Docker poll timed out (10s)")
        save_json(STATUS_FILE, {"docker_available": False, "timestamp": now}, caller="monitor")
        return
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to poll docker (Status {e.returncode})")
        if e.stderr:
            logger.error(f"DOCKER_STDERR: {e.stderr.strip()}")
        save_json(STATUS_FILE, {"docker_available": False, "error": str(e), "timestamp": now}, caller="monitor")
        return
    except Exception as e:
        logger.error(f"Failed to poll docker: {e}")
        save_json(STATUS_FILE, {"docker_available": False, "error": str(e), "timestamp": now}, caller="monitor")
        return

    containers_list = []
    for line in result.stdout.strip().split('\n'):
        if line:
            try:
                containers_list.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    health_status = {
        "docker_available": True,
        "containers": {},
        "timestamp": now
    }
    
    for target in targets:
        # Tweak 1: Safe fuzzy matching
        c = match_container_safe(target, containers_list)
        
        if c:
            # Tweak 2: State-based parsing (running vs exited vs restarting)
            state = c.get("State", "unknown").lower()
            status = c.get("Status", "unknown")
            
            if state == "running":
                m3_status = "online"
            elif state == "restarting":
                m3_status = "restarting"
            elif state in ["exited", "created", "paused"]:
                m3_status = "offline"
            else:
                # Fallback to status string if State is missing/unknown
                m3_status = "online" if "Up" in status else "offline"
                
            health_status["containers"][target] = {
                "status": m3_status,
                "raw_state": state,
                "raw_status": status,
                "created": c.get("CreatedAt")
            }
        else:
            # Truly missing (not found in ps -a even after fuzzy match)
            health_status["containers"][target] = {
                "status": "missing",
                "raw_status": "not found"
            }
            
    # Save to the per-agent file (Batch 5 T3)
    save_json(STATUS_FILE, health_status, caller="monitor")
    logger.info(f"Health check completed for {len(targets)} containers (Available: True).")

if __name__ == "__main__":
    import time
    wrap_agent("monitor", collect_health)
