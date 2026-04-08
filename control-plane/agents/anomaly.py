import sys
import os
import json

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON, NORMALIZED_METRICS_JSON, ANOMALIES_JSON
from utils.state import load_json, save_json
from utils.logger import get_logger

logger = get_logger("anomaly")

# Detection thresholds
CPU_THRESHOLD = 80.0

def detect_anomalies():
    try:
        anomalies = []
        
        # 1. Detect Exited Containers or Crash Loops from raw metrics (docker ps)
        # METRICS_JSON (from monitor.py) contains a list of container dicts
        container_data = load_json(METRICS_JSON, default=[])
        
        for container in container_data:
            name = container.get("Names", "unknown")
            state = container.get("State", "")
            status = container.get("Status", "")
            
            if state == "exited":
                anomalies.append({
                    "service": name,
                    "issue": "exited",
                    "detail": status
                })
                logger.warning(f"Detected EXITED container: {name}")
            elif "restarting" in status.lower():
                anomalies.append({
                    "service": name,
                    "issue": "crash_loop",
                    "detail": "restarting"
                })
                logger.warning(f"Detected CRASH_LOOP container: {name}")

        # 2. Detect High CPU from Normalized Metrics
        node_metrics = load_json(NORMALIZED_METRICS_JSON, default={})
        for node_name, data in node_metrics.items():
            cpu = data.get("cpu", 0)
            if cpu > CPU_THRESHOLD:
                anomalies.append({
                    "service": f"node:{node_name}",
                    "issue": "high_cpu",
                    "detail": f"{cpu}%"
                })
                logger.warning(f"Detected HIGH_CPU on node {node_name}: {cpu}%")

        if save_json(ANOMALIES_JSON, anomalies):
            if anomalies:
                logger.info(f"Saved {len(anomalies)} anomalies to {ANOMALIES_JSON}")
            else:
                logger.info("No anomalies detected.")
                
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")

if __name__ == "__main__":
    detect_anomalies()
