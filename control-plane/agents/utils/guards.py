import sys
import os
import time
from typing import Callable, Any

# Root addition for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import HEALTH_JSON
from utils.state import load_json, save_json
from utils.logger import get_logger

logger = get_logger("health")

def update_agent_health(agent_name: str, success: bool, error_msg: str = None):
    """Phase 5: Health Agent tracker"""
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
    """Phase 1: Exception Guard Wrapper"""
    agent_logger = get_logger(agent_name)
    try:
        agent_logger.info(f"--- Starting {agent_name} ---")
        func()
        update_agent_health(agent_name, success=True)
        agent_logger.info(f"--- Finished {agent_name} Successfully ---")
    except Exception as e:
        error_msg = str(e)
        agent_logger.error(f"FATAL ERROR in {agent_name}: {error_msg}", exc_info=True)
        update_agent_health(agent_name, success=False, error_msg=error_msg)
        # We don't exit(1) to keep the control loop alive as per Rule #2
