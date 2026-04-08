import sys
import os

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON, NORMALIZED_METRICS_JSON, ANOMALIES_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("anomaly")

CPU_THRESHOLD = 80.0

def detect_anomalies():
    anomalies = []
    
    # Phase 3: Pipeline Integrity - ensure valid structure
    container_data = load_json(METRICS_JSON, default=[])
    if not isinstance(container_data, list):
        logger.error(f"Integrity check failed: {METRICS_JSON} is not a list. Resetting.")
        container_data = []
        
    for container in container_data:
        name = container.get("Names", "unknown")
        state = container.get("State", "")
        status = container.get("Status", "")
        
        if state == "exited":
            anomalies.append({"service": name, "issue": "exited", "detail": status})
        elif "restarting" in status.lower():
            anomalies.append({"service": name, "issue": "crash_loop", "detail": "restarting"})

    # Check metrics integrity
    node_metrics = load_json(NORMALIZED_METRICS_JSON, default={})
    if not isinstance(node_metrics, dict):
        logger.error(f"Integrity check failed: {NORMALIZED_METRICS_JSON} should be dict.")
        node_metrics = {}

    for node_name, data in node_metrics.items():
        cpu = data.get("cpu", 0)
        if cpu > CPU_THRESHOLD:
            anomalies.append({"service": f"node:{node_name}", "issue": "high_cpu", "detail": f"{cpu}%"})

    save_json(ANOMALIES_JSON, anomalies)

if __name__ == "__main__":
    wrap_agent("anomaly", detect_anomalies)
