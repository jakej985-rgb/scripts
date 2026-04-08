import sys
import os
import time
import socket
from typing import Callable, Any

# Root addition for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import HEALTH_JSON, LEADER_TXT
from utils.state import load_json, save_json
from utils.logger import get_logger

logger = get_logger("guards")

def is_leader():
    """Batch 4 T1: Leadership Check"""
    if not os.path.exists(LEADER_TXT):
        return True # Default to leader if election hasn't run
    
    try:
        with open(LEADER_TXT, 'r') as f:
            leader_name = f.read().strip()
        
        # We are leader if leader.txt matches our hostname or 'localhost'
        my_name = socket.gethostname()
        return leader_name == my_name or leader_name == "localhost"
    except:
        return True

def update_agent_health(agent_name: str, success: bool, error_msg: str = None):
    health = load_json(HEALTH_JSON, default={})
    
    stats = health.get(agent_name, {
        "last_success": 0,
        "last_failure": 0,
        "failure_count": 0,
        "status": "unknown"
    })
    
    now = int(time.time())
    if success:
        stats["last_success"] = now
        stats["failure_count"] = 0
        stats["status"] = "healthy"
        stats["error"] = None
    else:
        stats["last_failure"] = now
        stats["failure_count"] += 1
        stats["status"] = "unstable" if stats["failure_count"] < 3 else "failing"
        stats["error"] = error_msg
        
    health[agent_name] = stats
    save_json(HEALTH_JSON, health)

def wrap_agent(agent_name: str, func: Callable[[], Any]):
    """Phase 1: Exception Guard Wrapper with Leadership Enforcement"""
    agent_logger = get_logger(agent_name)
    
    # Batch 4 T1: Only execute if we are the leader
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
