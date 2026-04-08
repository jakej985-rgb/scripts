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
LOCK_SUBDIR = os.path.join(STATE_DIR, "locks")

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

def acquire_lock(agent_name: str) -> bool:
    """Batch 15 T1: Ensure only one instance of an agent runs at a time."""
    os.makedirs(LOCK_SUBDIR, exist_ok=True)
    lock_file = os.path.join(LOCK_SUBDIR, f"{agent_name}.pid")
    
    # Check if lock exists and if the process is still alive
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Use kill(0) to check if process exists (Unix) or just assume Lock is stale if on Windows and PID isn't us
            if hasattr(os, 'kill'):
                os.kill(old_pid, 0)
                return False # Still alive
        except (ValueError, OSError):
            pass # Stale lock or Windows (fallback to overwrite)
            
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))
    return True

def release_lock(agent_name: str):
    lock_file = os.path.join(LOCK_SUBDIR, f"{agent_name}.pid")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except:
            pass

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

    if not acquire_lock(agent_name):
        agent_logger.warning(f"Agent {agent_name} already running (lock active). Exiting.")
        return

    try:
        agent_logger.info(f"--- Starting {agent_name} ---")
        func()
        update_agent_health(agent_name, success=True)
        agent_logger.info(f"--- Finished {agent_name} Successfully ---")
    finally:
        release_lock(agent_name)
        if _SHUTDOWN_SIGNALED:
            agent_logger.info(f"Agent {agent_name} released lock for shutdown.")
