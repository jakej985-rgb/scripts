import subprocess
import sys
import json
from pathlib import Path

# --- Path System Bootstrap ----------------------------------------------------
AGENTS_DIR = Path(__file__).resolve().parent  # control-plane/agents/
sys.path.append(str(AGENTS_DIR))

from utils.paths import STATE_DIR
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("network_guard")
GLUETUN_CONTAINER = "gluetun"
STATE_FILE = STATE_DIR / "network_guard_state.json"

def get_container_info(name):
    """Retrieves basic container info (ID and status)"""
    try:
        cmd = ["docker", "inspect", "-f", "{{.Id}}|{{.State.Status}}|{{.State.StartedAt}}", name]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            parts = res.stdout.strip().split('|')
            return {"id": parts[0], "status": parts[1], "started_at": parts[2]}
    except Exception:
        pass
    return None

def find_dependents():
    """Finds all containers configured with network_mode describing this gluetun container."""
    dependents = []
    try:
        # ps -a --format json provides NetworkMode directly in some Docker versions, 
        # but inspect is the cross-platform source of truth.
        cmd = ["docker", "ps", "-a", "--format", "{{.Names}}"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            names = [n.strip() for n in res.stdout.strip().splitlines() if n.strip()]
            for name in names:
                if name == GLUETUN_CONTAINER: continue
                
                # Check NetworkMode
                inspect_cmd = ["docker", "inspect", "-f", "{{.HostConfig.NetworkMode}}", name]
                inspect_res = subprocess.run(inspect_cmd, capture_output=True, text=True, timeout=5)
                if inspect_res.returncode == 0:
                    mode = inspect_res.stdout.strip()
                    if mode == f"container:{GLUETUN_CONTAINER}":
                        dependents.append(name)
    except Exception as e:
        logger.error(f"Error finding dependents: {e}")
    return dependents

def monitor_network():
    """Main loop: Detects Gluetun restarts and bounces dependents."""
    # 1. Load Last Known State
    last_state = {"id": None, "started_at": None}
    if STATE_FILE.exists():
        try:
            last_state = json.loads(STATE_FILE.read_text())
        except Exception:
            pass

    # 2. Get Current Gluetun Info
    current = get_container_info(GLUETUN_CONTAINER)
    if not current:
        logger.warning("Gluetun container not found. Is the network stack up?")
        return

    # 3. Detect Restart/Change
    if last_state["id"] and (current["id"] != last_state["id"] or current["started_at"] != last_state["started_at"]):
        logger.info(f"DETECTED Gluetun restart (StartedAt: {current['started_at']}). Bouncing dependents...")
        
        dependents = find_dependents()
        if not dependents:
            logger.info("No dependents found to restart.")
        else:
            for dep in dependents:
                try:
                    logger.info(f"Restarting dependent: {dep}")
                    subprocess.run(["docker", "restart", dep], check=True, timeout=30)
                except Exception as e:
                    logger.error(f"Failed to restart {dep}: {e}")
        
        logger.info("Dependents stabilized.")

    # 4. Save New State
    with open(STATE_FILE, "w") as f:
        json.dump(current, f)

if __name__ == "__main__":
    wrap_agent("network_guard", monitor_network)
