import os
import sys
import time
import json

# Standardize path resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, HEALTH_REPORT_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("scorer")
HEALTH_SUBDIR = os.path.join(STATE_DIR, "health")

# Files to check for corruption/freshness
MONITORED_FILES = [
    "metrics.json",
    "normalized_metrics.json",
    "anomalies.json",
    "decisions.json",
    "registry.json"
]

CHAOS_EVENTS_JSON = os.path.join(STATE_DIR, "chaos_events.json")
MAX_RECOVERY_TIME = 15

file_timer = {}
recovery_metrics = {"total_events": 0, "avg_ttr": 0, "failures": 0}

def get_file_status(path):
    if not os.path.exists(path):
        return "missing"
    data = load_json(path, default=None)
    if data is None:
        return "corrupt"
    return "ok"

def update_ttr(file_name, duration):
    events = load_json(CHAOS_EVENTS_JSON, default=[])
    changed = False
    for event in reversed(events):
        if event.get("target") == file_name and not event.get("resolved"):
            event["resolved"] = True
            event["ttr"] = int(duration)
            event["resolved_at"] = int(time.time())
            recovery_metrics["total_events"] += 1
            n = recovery_metrics["total_events"]
            recovery_metrics["avg_ttr"] = round((recovery_metrics["avg_ttr"] * (n-1) + duration) / n, 2)
            changed = True
            break
    if changed:
        save_json(CHAOS_EVENTS_JSON, events)

def aggregate_agent_health():
    """Batch 5 T3: Aggregate health from per-agent files."""
    aggregated = {}
    if os.path.isdir(HEALTH_SUBDIR):
        for f in os.listdir(HEALTH_SUBDIR):
            if f.endswith(".json"):
                agent_name = f.replace(".json", "")
                aggregated[agent_name] = load_json(os.path.join(HEALTH_SUBDIR, f))
    return aggregated

def calculate_health():
    score = 100
    file_issues = []
    now = time.time()
    
    # 1. File Health
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
                update_ttr(f_name, duration)
                if duration > MAX_RECOVERY_TIME:
                    file_issues.append(f"{f_name} slow recovery ({int(duration)}s)")
                    score -= 15
                del file_timer[f_name]

    # 2. Agent Health (Batch 5 T3 integration)
    agent_health = aggregate_agent_health()
    for agent, stats in agent_health.items():
        if stats.get("status") != "healthy":
            score -= 10
            file_issues.append(f"Agent Unhealthy: {agent} ({stats.get('error')})")
        # Staleness check
        if now - stats.get("timestamp", 0) > 120:
            score -= 15
            file_issues.append(f"Agent Stalled: {agent}")

    # 3. Pipeline Integrity
    decision_path = os.path.join(STATE_DIR, "decisions.json")
    if os.path.exists(decision_path):
        decision_data = load_json(decision_path, default={})
        meta_ts = decision_data.get("_m3tal_metadata", {}).get("updated_at", 0)
        age = now - meta_ts if meta_ts else 999
        if age > 120:
            file_issues.append("Pipeline Stall: decisions.json is stale")
            score -= 20

    score = max(score, 0)
    verdict = "HEALTHY" if score >= 85 else ("WARNING" if score >= 60 else "CRITICAL")
    
    # Export global health for API (backward compatibility)
    # The monitor_containers.json is merged here for dashboard consumption

    save_json(HEALTH_REPORT_JSON, {
        "score": score,
        "verdict": verdict,
        "issues": file_issues,
        "recovery": recovery_metrics,
        "agent_health": agent_health,
        "timestamp": int(now)
    })

if __name__ == "__main__":
    # Now uses wrap_agent for proper lock/shutdown/health integration (Audit fix 2.2)
    wrap_agent("scorer", calculate_health)
