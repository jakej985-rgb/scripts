import sys
import os

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import HEALTH_JSON, METRICS_JSON, ANOMALIES_JSON, HEALTH_REPORT_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("anomaly")

def classify_anomalies():
    """Phase 2: Advanced Anomaly Classification as per Audit Batch 2 T7."""
    health_data = load_json(HEALTH_JSON, default={})
    metrics_data = load_json(METRICS_JSON, default={})
    report_data = load_json(HEALTH_REPORT_JSON, default={})
    
    issues = []
    
    # 1. Container Health
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

    # 2. System Load (Now using deep metrics)
    system_metrics = metrics_data.get("system", {})
    cpu = system_metrics.get("cpu", 0)
    mem = system_metrics.get("mem", 0)
    
    if cpu > 90:
        issues.append({
            "type": "transient",
            "target": "host",
            "reason": f"CPU saturation: {cpu}%"
        })
    if mem > 95:
         issues.append({
            "type": "critical",
            "target": "host",
            "reason": f"Memory saturation: {mem}%"
        })

    # 3. Flapping / Stability Detection (Task T7 integration)
    # If the health report shows a warning/critical verdict, log it here
    if report_data.get("verdict") in ["WARNING", "CRITICAL"]:
        logger.warning(f"System health degraded: {report_data.get('verdict')} (Score: {report_data.get('score')}%)")

    # 4. Save
    save_json(ANOMALIES_JSON, {"issues": issues})
    if issues:
        logger.info(f"Identified {len(issues)} anomalies.")

if __name__ == "__main__":
    wrap_agent("anomaly", classify_anomalies)
