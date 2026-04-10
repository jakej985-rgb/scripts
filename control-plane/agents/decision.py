import sys
import os
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, ANOMALIES_JSON, DECISIONS_JSON, COOLDOWNS_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("decision")

# Cooldown to prevent flapping (Task 5)
COOLDOWN_PERIOD = 300  # 5 minutes

def plan_action(issues, cooldowns):
    """Core logic extracted for testability (Batch 7 T2)."""
    actions = []
    now = int(time.time())
    new_cooldowns = cooldowns.copy()
    
    for issue in issues:
        target = issue.get("target")
        issue_type = issue.get("type")
        
        if issue_type == "recoverable":
            # Check cooldown for this specific target
            last_action_time = cooldowns.get(target, 0)
            if now - last_action_time < COOLDOWN_PERIOD:
                continue
                
            # Differentiate between restart (stopped) and redeploy (missing)
            action_type = "restart"
            reason = issue.get("reason", "")
            if "missing" in reason:
                action_type = "redeploy"
                
            actions.append({
                "type": action_type,
                "target": target,
                "reason": reason
            })
            new_cooldowns[target] = now
            
        elif issue_type == "critical":
            logger.error(f"CRITICAL issue for {target}: {issue.get('reason')}. No automated action defined.")
            
    return actions, new_cooldowns

def decide():
    issues_data = load_json(ANOMALIES_JSON, default={"issues": []})
    cooldowns = load_json(COOLDOWNS_JSON, default={})
    
    actions, new_cooldowns = plan_action(issues_data.get("issues", []), cooldowns)
    
    save_json(DECISIONS_JSON, {"actions": actions})
    save_json(COOLDOWNS_JSON, new_cooldowns)
    
    if actions:
        logger.info(f"Decided on {len(actions)} actions.")

if __name__ == "__main__":
    wrap_agent("decision", decide)
