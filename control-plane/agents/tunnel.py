import subprocess
import os
import sys
import time
from pathlib import Path

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import REPO_ROOT, STATE_DIR
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("tunnel")
LOG_FILE = os.path.join(STATE_DIR, "logs", "tunnel.log")
CONTAINER_NAME = "cloudflared"
ROUTING_DIR = os.path.join(REPO_ROOT, "docker", "routing")

def check_tunnel_health():
    """
    Monitors the cloudflared container and performs autonomous repairs.
    """
    # 1. Check Container Status
    try:
        inspect_cmd = ["docker", "inspect", "-f", "{{.State.Status}}", CONTAINER_NAME]
        result = subprocess.run(inspect_cmd, capture_output=True, text=True)
        status = result.stdout.strip() if result.returncode == 0 else "missing"
    except Exception as e:
        logger.error(f"Failed to inspect tunnel container: {e}")
        status = "error"

    if status != "running":
        logger.warning(f"Tunnel container is {status}. Attempting recovery...")
        _recover_tunnel(status)
    else:
        # 2. Connectivity Check (Simple Ping to Cloudflare Edge)
        try:
            # We use a very short timeout for the ping check
            ping_cmd = ["docker", "exec", CONTAINER_NAME, "ping", "-c", "1", "cloudflare.com"]
            # On Windows host, if running in shell, ping works differently, but this is inside the container
            ping_result = subprocess.run(ping_cmd, capture_output=True, timeout=5)
            if ping_result.returncode == 0:
                logger.info("Tunnel connectivity verified.")
            else:
                logger.error("Tunnel container is running but cannot reach the edge.")
        except subprocess.TimeoutExpired:
            logger.error("Tunnel connectivity check timed out.")
        except Exception as e:
            logger.error(f"Failed to perform connectivity check: {e}")

def _recover_tunnel(current_status: str):
    """
    Performs autonomous recovery based on the container state.
    """
    try:
        if current_status == "missing":
            logger.info("Recreating missing tunnel container...")
            cmd = ["docker", "compose", "up", "-d", "cloudflared"]
            subprocess.run(cmd, cwd=ROUTING_DIR, check=True)
        else:
            logger.info(f"Restarting unhealthy tunnel container ({current_status})...")
            # Force recreate is safer for cloudflared to ensure token sync
            cmd = ["docker", "compose", "up", "-d", "--force-recreate", "cloudflared"]
            subprocess.run(cmd, cwd=ROUTING_DIR, check=True)
        
        logger.info("Tunnel recovery successful.")
    except Exception as e:
        logger.error(f"Tunnel recovery failed: {e}")

if __name__ == "__main__":
    # The wrap_agent keeps this running in a loop
    wrap_agent("tunnel", check_tunnel_health)
