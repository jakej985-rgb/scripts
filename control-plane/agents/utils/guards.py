import sys
import os
import time
import socket
import signal
from typing import Callable, Any

# Root addition for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, LEADER_TXT
from utils.state import load_json, save_json
from utils.logger import get_logger

logger = get_logger("guards")
HEALTH_SUBDIR = os.path.join(STATE_DIR, "health")

# Batch 8 T1: Graceful Shutdown
_SHUTDOWN_SIGNALED = False

def handle_signal(signum, frame):
    global _SHUTDOWN_SIGNALED
    logger.info(f"Received signal {signum}. Requesting graceful shutdown...")
    _SHUTDOWN_SIGNALED = True

# Register signals
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

def is_leader():
    if not os.path.exists(LEADER_TXT):
        return True
    try:
        with open(LEADER_TXT, 'r') as f:
            leader_name = f.read().strip()
        my_name = socket.gethostname()
        return leader_name == my_name or leader_name == "localhost"
    except:
        return True

def update_agent_health(agent_name: str, success: bool, error_msg: str = None):
    """Batch 5 T3: Write to per-agent health file to prevent race conditions."""
    os.makedirs(HEALTH_SUBDIR, exist_ok=True)
    path = os.path.join(HEALTH_SUBDIR, f"{agent_name}.json")
    
    now = int(time.time())
    stats = {
        "last_success": now if success else 0,
        "last_failure": now if not success else 0,
        "status": "healthy" if success else "failing",
        "error": error_msg,
        "timestamp": now,
        "shutdown": _SHUTDOWN_SIGNALED
    }
    
    save_json(path, stats)

def wrap_agent(agent_name: str, func: Callable[[], Any]):
    agent_logger = get_logger(agent_name)
    
    if _SHUTDOWN_SIGNALED:
        agent_logger.info(f"Agent {agent_name} skipping: Shutdown in progress.")
        return

    if not is_leader():
        agent_logger.debug(f"Skipping {agent_name}: Follower mode.")
        return

    try:
        agent_logger.info(f"--- Starting {agent_name} ---")
        func()
        update_agent_health(agent_name, success=True)
        agent_logger.info(f"--- Finished {agent_name} Successfully ---")
    except Exception as e:
        error_msg = str(e)
        agent_logger.error(f"FATAL ERROR in {agent_name}: {error_msg}", exc_info=True)
        update_agent_health(agent_name, success=False, error_msg=error_msg)
