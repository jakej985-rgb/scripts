import os
import sys
import time

# Standardize path resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, HEALTH_REPORT_JSON, TIERS
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("scorer")
HEALTH_SUBDIR = STATE_DIR / "health"


# Files to check for corruption/freshness
MONITORED_FILES = [
    "metrics.json",
    "normalized_metrics.json",
    "anomalies.json",
    "decisions.json",
    "registry.json"
]

CHAOS_EVENTS_JSON = STATE_DIR / "chaos_events.json"

MAX_RECOVERY_TIME = 15

file_timer = {}
recovery_metrics = {"total_events": 0, "avg_ttr": 0, "failures": 0}

def get_file_status(path):
    if not path.exists():
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
        save_json(CHAOS_EVENTS_JSON, events, caller="health_score")

def aggregate_agent_health():
    """Batch 5 T3: Aggregate health from per-agent files."""
    aggregated = {}
    if HEALTH_SUBDIR.is_dir():
        for f in os.listdir(HEALTH_SUBDIR):
            if f.endswith(".json"):
                agent_name = f.replace(".json", "")
                # Security: Only aggregate files that are known agents (Audit Fix 2)
                if agent_name in TIERS or agent_name == "monitor_containers":
                    aggregated[agent_name] = load_json(HEALTH_SUBDIR / f)
                else:
                    logger.warning(f"Security: Ignored health file from unknown agent: {agent_name}")

    return aggregated

def calculate_health():
    score = 100
    file_issues = []
    now = time.time()
    
    # Tweak 5: Health Modes & Docker Guard
    monitor_path = STATE_DIR / "health" / "monitor_containers.json"
    monitor_data = load_json(monitor_path, default={"docker_available": True})

    docker_available = monitor_data.get("docker_available", True)
    
    # 1. File Health
    for f_name in MONITORED_FILES:
        path = STATE_DIR / f_name
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
    tier1_agents = [name for name, tier in TIERS.items() if tier == 1]
    tier1_fail = False
    
    for agent, stats in agent_health.items():
        if agent == "monitor_containers":
            continue

        # Skip stale/unhealthy penalties for agents in graceful shutdown
        if stats.get("shutdown"):
            continue
            
        if stats.get("status") != "healthy":
            score -= 10
            file_issues.append(f"Agent Unhealthy: {agent} ({stats.get('error')})")
            if agent in tier1_agents:
                tier1_fail = True
        
        # Staleness check
        if now - stats.get("timestamp", 0) > 120:
            score -= 15
            file_issues.append(f"Agent Stalled: {agent}")
            if agent in tier1_agents:
                tier1_fail = True

    # 3. Pipeline Integrity
    decision_path = STATE_DIR / "decisions.json"
    if decision_path.exists():
        decision_data = load_json(decision_path, default={})
        meta_ts = decision_data.get("_m3tal_metadata", {}).get("updated_at", 0)
        age = now - meta_ts if meta_ts else 999
        if age > 120:
            file_issues.append("Pipeline Stall: decisions.json is stale")
            score -= 20
            tier1_fail = True

    # 4. Hardware Observability (Temperature & Storage)
    from utils.paths import TEMP_JSON, STORAGE_JSON
    
    if TEMP_JSON.exists():
        temp_data = load_json(TEMP_JSON, default={})
        t_status = temp_data.get("status", "healthy")
        if t_status == "critical":
            score -= 25
            file_issues.append("Hardware: CRITICAL Temperature Detected")
        elif t_status == "warning":
            score -= 10
            file_issues.append("Hardware: Warning Temperature Detected")
            
    if STORAGE_JSON.exists():
        storage_data = load_json(STORAGE_JSON, default={})
        s_status = storage_data.get("status", "healthy")
        if s_status == "critical":
            score -= 25
            file_issues.append("Hardware: CRITICAL Disk Usage Detected")
        elif s_status == "warning":
            score -= 10
            file_issues.append("Hardware: Warning Disk Usage Detected")

    # 4. Mode Determination (Tweak 5)
    any_agent_fail = any(stats.get("status") != "healthy" for agent, stats in agent_health.items() if agent != "monitor_containers")
    
    if tier1_fail:
        mode = "CRITICAL"
        score = min(score, 40)
    elif any_agent_fail:
        mode = "DEGRADED"
        score = min(score, 70)
    elif not docker_available:
        mode = "PARTIAL"
        score = max(score, 70) 
        file_issues.append("DOCKER_UNREACHABLE: No container visibility")
    else:
        mode = "FULL"

    score = max(score, 0)
    
    save_json(HEALTH_REPORT_JSON, {
        "score": score,
        "mode": mode,
        "verdict": mode,
        "issues": file_issues,
        "recovery": recovery_metrics,
        "agent_health": agent_health,
        "docker_available": docker_available,
        "timestamp": int(now)
    }, caller="health_score")
    
    logger.info(f"Health check completed. Mode: {mode}, Score: {score}")

def check_docker_connectivity():
    """Initial guard check for Docker daemon."""
    import subprocess
    try:
        subprocess.run(["docker", "ps", "-q"], capture_output=True, timeout=5, check=True)
        return True
    except Exception:
        return False

if __name__ == "__main__":
    if not check_docker_connectivity():
        logger.warning("Docker daemon unreachable at startup. System will start in PARTIAL mode.")
    
    wrap_agent("health_score", calculate_health)
