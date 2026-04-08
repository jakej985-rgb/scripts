import sys
import os
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON, STATE_DIR, DECISIONS_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("scaling")
SCALING_CONFIG = os.path.join(STATE_DIR, "scaling.json")

def evaluate_scaling():
    """Phase 1: Scaling Agent as per Audit Batch 4 T2."""
    metrics = load_json(METRICS_JSON, default={})
    scaling_rules = load_json(SCALING_CONFIG, default={})
    
    if not metrics or not scaling_rules:
        logger.debug("Missing metrics or scaling rules. Skipping.")
        return

    container_metrics = metrics.get("containers", [])
    # Convert list to dict for lookup
    stats = {c.get("name"): c for c in container_metrics}
    
    decisions = load_json(DECISIONS_JSON, default={"actions": []})
    new_actions = []
    
    for service, rules in scaling_rules.items():
        if service not in stats:
            continue
            
        current_cpu = stats[service].get("cpu", 0)
        min_reps = rules.get("min", 1)
        max_reps = rules.get("max", 1)
        up_threshold = rules.get("cpu_up", 80)
        down_threshold = rules.get("cpu_down", 20)
        
        # Note: Scaler doesn't know current replica count yet (future T3)
        # For now, it issues 'scale' recommendations
        
        if current_cpu > up_threshold:
            logger.warning(f"Scaling UP {service}: CPU {current_cpu}% > {up_threshold}%")
            new_actions.append({
                "type": "scale",
                "target": service,
                "direction": "up",
                "image": rules.get("image"),
                "reason": f"CPU High: {current_cpu}%"
            })
        elif current_cpu < down_threshold:
            logger.info(f"Scaling DOWN {service}: CPU {current_cpu}% < {down_threshold}%")
            new_actions.append({
                "type": "scale",
                "target": service,
                "direction": "down",
                "reason": f"CPU Idle: {current_cpu}%"
            })

    if new_actions:
        # Merge with existing decisions
        decisions["actions"].extend(new_actions)
        save_json(DECISIONS_JSON, decisions)
        logger.info(f"Issued {len(new_actions)} scaling recommendations.")

if __name__ == "__main__":
    wrap_agent("scaling", evaluate_scaling)
