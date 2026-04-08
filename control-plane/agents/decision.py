import sys
import os
import json

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import ANOMALIES_JSON, DECISIONS_JSON
from utils.state import load_json, save_json
from utils.logger import get_logger

logger = get_logger("decision")

def make_decisions():
    try:
        # Load detected anomalies
        anomalies = load_json(ANOMALIES_JSON, default=[])
        
        decisions = {"actions": []}
        seen_services = set()
        
        for anomaly in anomalies:
            service = anomaly.get("service")
            issue = anomaly.get("issue")
            
            # Deduplication
            if service in seen_services:
                continue
            
            action = None
            priority = 1
            
            if issue in ["exited", "crash_loop"]:
                action = "restart"
                priority = 3 # High priority for down services
            elif issue == "high_cpu":
                action = "scale_up"
                priority = 2 # Medium priority for performance
                
            if action:
                decisions["actions"].append({
                    "service": service,
                    "action": action,
                    "priority": priority,
                    "reason": issue
                })
                seen_services.add(service)
                logger.info(f"Queued action: {action} for {service} (priority: {priority})")

        # Sort by priority descending
        decisions["actions"].sort(key=lambda x: x['priority'], reverse=True)

        if save_json(DECISIONS_JSON, decisions):
            logger.info(f"Saved {len(decisions['actions'])} decisions to {DECISIONS_JSON}")
            
    except Exception as e:
        logger.error(f"Decision engine failed: {e}")

if __name__ == "__main__":
    make_decisions()
