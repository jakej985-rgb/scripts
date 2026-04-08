import sys
import os

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import ANOMALIES_JSON, DECISIONS_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("decision")

def make_decisions():
    # Phase 3: Pipeline Integrity
    anomalies = load_json(ANOMALIES_JSON, default=[])
    if not isinstance(anomalies, list):
        logger.error(f"Invalid anomalies format in {ANOMALIES_JSON}")
        anomalies = []
        
    decisions = {"actions": []}
    seen_services = set()
    
    for anomaly in anomalies:
        service = anomaly.get("service")
        issue = anomaly.get("issue")
        if not service or service in seen_services: continue
        
        action = None
        priority = 1
        
        if issue in ["exited", "crash_loop"]:
            action = "restart"; priority = 3
        elif issue == "high_cpu":
            action = "scale_up"; priority = 2
            
        if action:
            decisions["actions"].append({
                "service": service,
                "action": action,
                "priority": priority,
                "reason": issue
            })
            seen_services.add(service)

    decisions["actions"].sort(key=lambda x: x['priority'], reverse=True)
    save_json(DECISIONS_JSON, decisions)

if __name__ == "__main__":
    wrap_agent("decision", make_decisions)
