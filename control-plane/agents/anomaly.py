import sys
import os

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import HEALTH_JSON, METRICS_JSON, ANOMALIES_JSON, HEALTH_REPORT_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("anomaly")

def safe_get(obj, key, default=None):
    """Batch 7 T2: Safe dictionary access guard."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

def classify_issue(health_data, metrics_data, report_data=None):
    """Core logic extracted for testability (Batch 7 T2)."""
    issues = []
    
    if not isinstance(health_data, dict):
        logger.error(f"Invalid health_data type: {type(health_data)}")
        return issues

    # 1. Container Health
    for name, info in health_data.items():
        # Audit fix 2.12: Ignore metadata and skip non-dict entries
        if name == "_m3tal_metadata" or not isinstance(info, dict):
            continue
            
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
    if not isinstance(metrics_data, dict):
        logger.error(f"Invalid metrics_data type: {type(metrics_data)}")
        return issues

    system_metrics = safe_get(metrics_data, "system", {})
    cpu = safe_get(system_metrics, "cpu", 0)
    mem = safe_get(system_metrics, "mem", 0)
    
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

    # 3. Aggregated per-container resource alerts
    containers = safe_get(metrics_data, "containers", [])
    if isinstance(containers, list):
        for c in containers:
             if not isinstance(c, dict): continue
             if safe_get(c, "cpu", 0) > 90:
                 issues.append({
                    "type": "resource_spike",
                    "target": safe_get(c, "name", "unknown"),
                    "reason": f"High Container CPU: {safe_get(c, 'cpu', 0)}%"
                })

    return issues

def analyze():
    health_data = load_json(HEALTH_JSON, default={})
    metrics_data = load_json(METRICS_JSON, default={})
    report_data = load_json(HEALTH_REPORT_JSON, default={})
    
    try:
        issues = classify_issue(health_data, metrics_data, report_data)
    except Exception as e:
        logger.error(f"Anomaly analysis failed: {e}")
        issues = []
    
    if report_data.get("verdict") in ["WARNING", "CRITICAL"]:
        logger.warning(f"System health degraded: {report_data.get('verdict')} (Score: {report_data.get('score')}%)")

    save_json(ANOMALIES_JSON, {"issues": issues})
    if issues:
        logger.info(f"Identified {len(issues)} anomalies.")

if __name__ == "__main__":
    wrap_agent("anomaly", analyze)
