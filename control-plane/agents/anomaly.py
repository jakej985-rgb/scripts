import sys
import os

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("anomaly")
HEALTH_JSON = os.path.join(STATE_DIR, "health.json")
METRICS_JSON = os.path.join(STATE_DIR, "metrics.json")
ANOMALIES_JSON = os.path.join(STATE_DIR, "anomalies.json")

def classify_anomalies():
    """Phase 2: Anomaly Classification as per Task 4."""
    health_data = load_json(HEALTH_JSON, default={})
    metrics_data = load_json(METRICS_JSON, default={})
    
    issues = []
    
    # Check container health
    for name, info in health_data.items():
        status = info.get("status")
        if status == "offline":
            issues.append({
                "type": "recoverable",
                "target": name,
                "reason": "container stopped"
            })
        elif status == "missing":
            issues.append({
                "type": "critical",
                "target": name,
                "reason": "container definition missing or not created"
            })

    # Check system metrics
    cpu = metrics_data.get("cpu", 0)
    if cpu > 90:
        issues.append({
            "type": "transient",
            "target": "host",
            "reason": f"extreme cpu load: {cpu}%"
        })
    elif cpu > 70:
        logger.warning(f"CPU load moderate: {cpu}%")

    output = {"issues": issues}
    save_json(ANOMALIES_JSON, output)
    if issues:
        logger.info(f"Detected {len(issues)} issues.")

if __name__ == "__main__":
    wrap_agent("anomaly", classify_anomalies)
