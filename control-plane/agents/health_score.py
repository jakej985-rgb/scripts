import os
import sys
import time
import json

# Standardize path resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, HEALTH_JSON, HEALTH_REPORT_JSON
from utils.state import load_json, save_json
from utils.logger import get_logger

logger = get_logger("scorer")

# Files to check for corruption/freshness
MONITORED_FILES = [
    "metrics.json",
    "normalized_metrics.json",
    "anomalies.json",
    "decisions.json",
    "registry.json"
]

MAX_RECOVERY_TIME = 15  # seconds
CHECK_INTERVAL = 5

file_timer = {}
last_known_status = {}

def get_file_status(path):
    if not os.path.exists(path):
        return "missing"
    data = load_json(path, default=None)
    if data is None:
        return "corrupt"
    return "ok"

def monitor_recovery(file_name, status):
    """Integrated recovery_check.py functionality."""
    prev = last_known_status.get(file_name)
    if prev and prev != status:
        logger.info(f"FILE STATUS CHANGE: {file_name} from {prev} to {status}")
    last_known_status[file_name] = status

def calculate_health():
    """Phase 2: Unified Health/Anomaly as per Audit Batch 2 T6/T7."""
    score = 100
    file_issues = []
    
    # 1. File Health Core
    for f_name in MONITORED_FILES:
        path = os.path.join(STATE_DIR, f_name)
        status = get_file_status(path)
        
        # Log changes (recovery_check integration)
        monitor_recovery(f_name, status)

        if status in ["missing", "corrupt"]:
            if f_name not in file_timer:
                file_timer[f_name] = time.time()
            score -= 5
        else:
            if f_name in file_timer:
                duration = time.time() - file_timer[f_name]
                if duration > MAX_RECOVERY_TIME:
                    file_issues.append(f"{f_name} exceeded recovery SLA ({int(duration)}s)")
                    score -= 15
                del file_timer[f_name]

    # 2. Pipeline Integrity (Staleness)
    decision_path = os.path.join(STATE_DIR, "decisions.json")
    if os.path.exists(decision_path):
        age = time.time() - os.path.getmtime(decision_path)
        if age > 60:
            file_issues.append("Pipeline Stall: decisions.json is stale (>60s)")
            score -= 20

    # 3. Final Verdict
    score = max(score, 0)
    verdict = "HEALTHY" if score >= 85 else ("WARNING" if score >= 60 else "CRITICAL")
    
    logger.info(f"System Health Score: {score}% | Verdict: {verdict}")
    if file_issues:
        for issue in file_issues:
            logger.warning(f"Health issue: {issue}")

    # 4. Save State
    save_json(HEALTH_REPORT_JSON, {
        "score": score,
        "verdict": verdict,
        "issues": file_issues,
        "timestamp": int(time.time()),
        "file_states": last_known_status
    })

if __name__ == "__main__":
    logger.info("Health Scorer Active (Consolidated)")
    try:
        while True:
            calculate_health()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(f"Health Scorer CRASHED: {e}", exc_info=True)
