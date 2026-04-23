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

        # Audit Fix M5: Warmup guard - don't scale down if just started
        from utils.paths import REGISTRY_JSON
        registry = load_json(REGISTRY_JSON, default={})
        started_at_str = registry.get("stacks", {}).get(service, {}).get("started_at", "0")
        try:
            # Docker StartedAt is ISO format: 2026-04-23T06:06:00Z
            import datetime
            # Basic parse (handle Z or offset)
            ts_str = started_at_str.split('.')[0].rstrip('Z')
            started_ts = datetime.datetime.fromisoformat(ts_str).timestamp()
            uptime = now - started_ts
            if uptime < 600: # 10 minute warmup
                continue
        except Exception:
            pass

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

    # Merge with existing actions to prevent loss (Audit Fix 6.6 — M7 Merge)
    existing_data = load_json(SCALING_ACTIONS, default={"actions": []})
    existing_actions = existing_data.get("actions", [])
    
    # Simple merge: use a dict to deduplicate by {type}:{target} (Audit Fix 5)
    merged = {(a["type"], a["target"]): a for a in existing_actions}
    for a in new_actions:
        merged[(a["type"], a["target"])] = a
        
    final_actions = list(merged.values())

    if final_actions:
        save_json(SCALING_ACTIONS, {"actions": final_actions}, caller="scaling")
        save_json(COOLDOWN_FILE, cooldowns, caller="scaling")
        logger.info(f"Updated scaling queue: {len(final_actions)} actions pending.")
    else:
        # Only clear if we explicitly have nothing new and nothing existing
        if existing_actions:
            save_json(SCALING_ACTIONS, {"actions": []}, caller="scaling")


if __name__ == "__main__":
    wrap_agent("scaling", evaluate_scaling)
