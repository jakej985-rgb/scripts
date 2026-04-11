import sys
import os
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON, STATE_DIR
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("scaling")
SCALING_CONFIG = os.path.join(STATE_DIR, "scaling.json")
SCALING_ACTIONS = os.path.join(STATE_DIR, "scaling_actions.json")

# Batch 5 T4: Persistent cooldown state
COOLDOWN_FILE = os.path.join(STATE_DIR, "scaling_cooldowns.json")
GLOBAL_COOLDOWN = 300 # 5 minutes

def evaluate_scaling():
    """Phase 1: Scaling Agent with Cooldown support as per Batch 5 T4."""
    metrics = load_json(METRICS_JSON, default={})
    scaling_rules = load_json(SCALING_CONFIG, default={})
    cooldowns = load_json(COOLDOWN_FILE, default={})
    
    if not metrics or not scaling_rules:
        return

    container_metrics = metrics.get("containers", [])
    stats = {c.get("name"): c for c in container_metrics}
    
    new_actions = []
    now = int(time.time())
    
    for service, rules in scaling_rules.items():
        if service not in stats: continue
            
        # Cooldown check
        last_action = cooldowns.get(service, 0)
        if now - last_action < GLOBAL_COOLDOWN:
            continue

        current_cpu = stats[service].get("cpu", 0)
        up_threshold = rules.get("cpu_up", 80)
        down_threshold = rules.get("cpu_down", 20)
        
        action = None
        if current_cpu > up_threshold:
            action = "up"
            logger.warning(f"Scaling UP {service}")
        elif current_cpu < down_threshold:
            action = "down"
            logger.info(f"Scaling DOWN {service}")

        if action:
            new_actions.append({
                "type": "scale",
                "target": service,
                "direction": action,
                "image": rules.get("image"),
                "reason": f"CPU trigger: {current_cpu}%"
            })
            cooldowns[service] = now

    if new_actions:
        # Write to own state file to avoid racing with decision.py (Audit fix 2.3)
        save_json(SCALING_ACTIONS, {"actions": new_actions}, caller="scaling")
        save_json(COOLDOWN_FILE, cooldowns, caller="scaling")
        logger.info(f"Issued {len(new_actions)} scaling actions.")
    else:
        # Clear stale scaling actions
        save_json(SCALING_ACTIONS, {"actions": []}, caller="scaling")

if __name__ == "__main__":
    wrap_agent("scaling", evaluate_scaling)
