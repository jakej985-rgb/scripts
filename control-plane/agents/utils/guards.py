import sys
import os
import time
import signal
from typing import Callable, Any

# Root addition for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, LEADER_TXT
from utils.identity import is_local_host
from utils.state import save_json
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
        return is_local_host(leader_name)
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
            
            alive = False
            try:
                import psutil
                if psutil.pid_exists(old_pid):
                    proc = psutil.Process(old_pid)
                    # Safety check: ensure it's actually a python/agent process
                    if proc.is_running() and "python" in proc.name().lower():
                        alive = True
            except (ImportError, Exception):
                # Fallback to os.kill(0) if psutil fails or is missing
                if hasattr(os, 'kill'):
                    try:
                        os.kill(old_pid, 0)
                        alive = True
                    except OSError:
                        alive = False
                else:
                    # Windows without psutil: assume stale
                    alive = False

            if alive:
                return False

            try:
                os.remove(lock_file)
            except OSError:
                pass
        except (ValueError, OSError):
            try:
                os.remove(lock_file)
            except OSError:
                pass
            
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

def wrap_agent(agent_name: str, func: Callable[[], Any], interval: int = 10):
    """Batch 16 T1: Persistent Agent Wrapper with internal looping and signal handling."""
    agent_logger = get_logger(agent_name)
    
    if not acquire_lock(agent_name):
        agent_logger.warning(f"Agent {agent_name} already running (lock active). Exiting.")
        return

    try:
        agent_logger.info(f"--- Agent {agent_name} Persistent Loop Started ---")
        
        while not _SHUTDOWN_SIGNALED:
            if not is_leader():
                # Follower mode: sleep and check again later
                time.sleep(interval)
                continue

            try:
                # Execution tick
                func()
                update_agent_health(agent_name, success=True)
            except Exception as e:
                agent_logger.error(f"Agent {agent_name} tick failed: {e}", exc_info=True)
                update_agent_health(agent_name, success=False, error_msg=str(e))
                # Exponential-ish backoff on error would be here, 
                # but we rely on the loop interval for now.

            # Sleep until next tick
            for _ in range(interval):
                if _SHUTDOWN_SIGNALED:
                    break
                time.sleep(1)

        agent_logger.info(f"--- Agent {agent_name} Shutdown Cleanly ---")
    finally:
        release_lock(agent_name)
