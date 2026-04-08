import os
import sys
import time
import json

# Standardize path resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, HEALTH_REPORT_JSON
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

CHAOS_EVENTS_JSON = os.path.join(STATE_DIR, "chaos_events.json")
MAX_RECOVERY_TIME = 15  # seconds
CHECK_INTERVAL = 5

file_timer = {}
last_known_status = {}
recovery_metrics = {"total_events": 0, "avg_ttr": 0, "failures": 0}

def get_file_status(path):
    if not os.path.exists(path):
        return "missing"
    data = load_json(path, default=None)
    if data is None:
        return "corrupt"
    return "ok"

def update_ttr(file_name, duration):
    """T5: Calculate Time-To-Recovery (TTR) based on chaos events."""
    events = load_json(CHAOS_EVENTS_JSON, default=[])
    changed = False
    for event in reversed(events):
        if event.get("target") == file_name and not event.get("resolved"):
            event["resolved"] = True
            event["ttr"] = int(duration)
            event["resolved_at"] = int(time.time())
            
            # Update global stats
            recovery_metrics["total_events"] += 1
            n = recovery_metrics["total_events"]
            prev_avg = recovery_metrics["avg_ttr"]
            recovery_metrics["avg_ttr"] = round((prev_avg * (n-1) + duration) / n, 2)
            
            logger.info(f"✅ RECOVERY SUCCESS: {file_name} in {int(duration)}s")
            changed = True
            break
    
    if changed:
        save_json(CHAOS_EVENTS_JSON, events)

def calculate_health():
    """Phase 2: Unified Health/Anomaly with TTR Monitoring."""
    score = 100
    file_issues = []
    now = time.time()
    
    # 1. File Health Core
    for f_name in MONITORED_FILES:
        path = os.path.join(STATE_DIR, f_name)
        status = get_file_status(path)
        
        if status in ["missing", "corrupt"]:
            if f_name not in file_timer:
                file_timer[f_name] = now
            score -= 5
        else:
            if f_name in file_timer:
                duration = now - file_timer[f_name]
                update_ttr(f_name, duration) # Log recovery metrics
                
                if duration > MAX_RECOVERY_TIME:
                    file_issues.append(f"{f_name} slow recovery ({int(duration)}s)")
                    score -= 15
                del file_timer[f_name]

    # 2. Pipeline Integrity
    decision_path = os.path.join(STATE_DIR, "decisions.json")
    if os.path.exists(decision_path):
        age = now - os.path.getmtime(decision_path)
        if age > 60:
            file_issues.append("Pipeline Stall: decisions.json is stale (>60s)")
            score -= 20

    # 3. Final Verdict
    score = max(score, 0)
    verdict = "HEALTHY" if score >= 85 else ("WARNING" if score >= 60 else "CRITICAL")
    
    logger.info(f"Score: {score}% | TTR Avg: {recovery_metrics['avg_ttr']}s")

    # 4. Save State
    save_json(HEALTH_REPORT_JSON, {
        "score": score,
        "verdict": verdict,
        "issues": file_issues,
        "recovery": recovery_metrics,
        "timestamp": int(now)
    })

if __name__ == "__main__":
    logger.info("Health Scorer Active (TTR Tracking enabled)")
    try:
        while True:
            calculate_health()
            time.sleep(CHECK_INTERVAL)
    except Exception as e:
        logger.critical(f"Health Scorer CRASHED: {e}")
