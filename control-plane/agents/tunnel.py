import subprocess
import os
import sys
import time
from pathlib import Path

# --- Path System Bootstrap ----------------------------------------------------
AGENTS_DIR = Path(__file__).resolve().parent  # control-plane/agents/
sys.path.append(str(AGENTS_DIR))

from utils.paths import REPO_ROOT, STATE_DIR, LOG_DIR, DOCKER_DIR
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("tunnel")
LOG_FILE = LOG_DIR / "tunnel.log"
CONTAINER_NAME = "cloudflared"
ROUTING_DIR = DOCKER_DIR / "routing"

def check_tunnel_health():
    """Monitors the cloudflared container and performs autonomous repairs."""
    # 0. Config Gate: Do not attempt recovery if essential env is missing
    token = os.getenv("CF_TUNNEL_TOKEN")
    domain = os.getenv("DOMAIN")
    
    if not token or not domain:
        logger.warning(f"Tunnel config missing (Token={bool(token)}, Domain={bool(domain)}). Skipping cycle.")
        return
    # 1. Check Container Status
    try:
        inspect_cmd = ["docker", "inspect", "-f", "{{.State.Status}}", CONTAINER_NAME]
        # Tweak 4: Subprocess timeout
        result = subprocess.run(inspect_cmd, capture_output=True, text=True, timeout=10)
        status = result.stdout.strip() if result.returncode == 0 else "missing"
    except subprocess.TimeoutExpired:
        logger.error("Tunnel inspect timed out (10s)")
        status = "error"
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
            subprocess.run(cmd, cwd=ROUTING_DIR, check=True, timeout=60)
        else:
            logger.info(f"Restarting unhealthy tunnel container ({current_status})...")
            # Force recreate is safer for cloudflared to ensure token sync
            cmd = ["docker", "compose", "up", "-d", "--force-recreate", "cloudflared"]
            subprocess.run(cmd, cwd=ROUTING_DIR, check=True, timeout=60)
        
        logger.info("Tunnel recovery successful.")
    except subprocess.TimeoutExpired:
        logger.error("Tunnel recovery timed out (60s)")
    except Exception as e:
        logger.error(f"Tunnel recovery failed: {e}")

if __name__ == "__main__":
    # The wrap_agent keeps this running in a loop
    wrap_agent("tunnel", check_tunnel_health)
