import sys
import os
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("decision")
ANOMALIES_JSON = os.path.join(STATE_DIR, "anomalies.json")
DECISIONS_JSON = os.path.join(STATE_DIR, "decisions.json")
COOLDOWNS_JSON = os.path.join(STATE_DIR, "cooldowns.json")

# Cooldown to prevent flapping (Task 5)
COOLDOWN_PERIOD = 300  # 5 minutes

def make_decisions():
    """Phase 2: Decision Engine with Cooldown system as per Task 5."""
    issues_data = load_json(ANOMALIES_JSON, default={"issues": []})
    cooldowns = load_json(COOLDOWNS_JSON, default={})
    
    issues = issues_data.get("issues", [])
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
                logger.info(f"Cooldown active for {target}. Skipping restart action.")
                continue
                
            actions.append({
                "type": "restart",
                "target": target,
                "reason": issue.get("reason")
            })
            # Update cooldown timestamp
            new_cooldowns[target] = now
            
        elif issue_type == "critical":
            logger.error(f"CRITICAL issue for {target}: {issue.get('reason')}. No automated action defined.")
    
    # Task 3: Writes choices to decisions.json
    save_json(DECISIONS_JSON, {"actions": actions})
    save_json(COOLDOWNS_JSON, new_cooldowns)
    
    if actions:
        logger.info(f"Decidied on {len(actions)} actions.")

if __name__ == "__main__":
    wrap_agent("decision", make_decisions)
